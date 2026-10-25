"""
Polymorphic Graph Crawler for FHIR Bundles
Implements:
1. Recursive reference extraction across any depth of the FHIR JSON model:
   - Relative: 'Patient/123'
   - URN: 'urn:uuid:123e4567-e89b-12d3-a456-426614174000'
   - Contained: '#med-1'
2. Clinical node hierarchy weighting for ForceGraph2D:
   - Patient at the core (weight 28)
   - Encounter (weight 20)
   - Clinical items: Condition, Observation, MedicationRequest (weight 14)
   - Contained items (weight 10)
"""

from typing import Dict, Any, List, Set, Tuple

def normalize_reference(raw_ref: str) -> str:
    """
    Normalizes FHIR references of all standard formats:
    - 'urn:uuid:11cf2c74-80b3-581c-9662-e3bc4cb4c087' -> returns UUID
    - 'Patient/123' -> returns '123'
    - '#med-1' -> returns 'med-1'
    """
    if not raw_ref:
        return ""
    ref_str = str(raw_ref).strip()
    if ref_str.startswith("urn:uuid:"):
        return ref_str.replace("urn:uuid:", "")
    if "#" in ref_str:
        return ref_str.split("#")[-1]
    if "/" in ref_str:
        return ref_str.split("/")[-1]
    return ref_str

def extract_references_recursive(obj: Any, parent_key: str = "") -> List[Tuple[str, str]]:
    """
    Recursively traverses arbitrary nested FHIR objects/arrays to extract
    every pointer string matching {"reference": "..."}.
    Returns list of (relation_name, target_reference_string).
    """
    refs = []
    if isinstance(obj, dict):
        if "reference" in obj and isinstance(obj["reference"], str) and obj["reference"]:
            refs.append((parent_key or "reference", obj["reference"]))
        for k, v in obj.items():
            if k != "reference":
                refs.extend(extract_references_recursive(v, parent_key=k))
    elif isinstance(obj, list):
        for item in obj:
            refs.extend(extract_references_recursive(item, parent_key=parent_key))
    return refs

def get_node_label(resource: Dict[str, Any]) -> Tuple[str, str]:
    """Generates clean primary and secondary clinical display labels."""
    rtype = resource.get("resourceType", "Resource")
    rid = str(resource.get("id", ""))[:8]
    sub = ""

    if rtype == "Patient":
        names = resource.get("name", [{}])[0]
        given = " ".join(names.get("given", []))
        family = names.get("family", "")
        primary = f"Patient: {given} {family}".strip() if (given or family) else f"Patient (#{rid})"
        sub = f"MRN: {resource.get('identifier', [{}])[0].get('value', 'N/A')}"
    elif rtype == "Encounter":
        enc_cls = resource.get("class", {})
        cls_code = enc_cls.get("display") or enc_cls.get("code") or "Clinical Visit"
        primary = f"Encounter: {cls_code}"
        period = resource.get("period", {}).get("start", "")[:10]
        sub = f"Date: {period} | Status: {resource.get('status', 'in-progress')}"
    elif rtype == "Condition":
        code_obj = resource.get("code", {})
        code_txt = code_obj.get("text") or code_obj.get("coding", [{}])[0].get("display") or "Diagnosis"
        primary = f"Condition: {code_txt}"
        clin_stat = resource.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "active")
        sub = f"Status: {clin_stat.capitalize()}"
    elif rtype == "Observation":
        code_obj = resource.get("code", {})
        test_name = code_obj.get("text") or code_obj.get("coding", [{}])[0].get("display") or "Lab Result"
        val = resource.get("valueQuantity", {})
        val_str = f"{val.get('value', '')} {val.get('unit', '')}".strip() if val else resource.get("valueString", "")
        primary = f"Obs: {test_name}"
        sub = f"Value: {val_str}" if val_str else "Observation"
    elif rtype == "MedicationRequest":
        med = resource.get("medicationReference", {}).get("display") or resource.get("medicationCodeableConcept", {}).get("text") or "Medication"
        primary = f"Rx: {med}"
        dosages = resource.get("dosageInstruction", [])
        sub = dosages[0].get("text", "Active order") if dosages else "Active order"
    elif rtype == "Claim":
        tot = resource.get("total", {})
        tot_str = f"${tot.get('value', 0):.2f}"
        primary = f"Claim (#{rid})"
        sub = f"Total: {tot_str}"
    elif rtype == "Coverage":
        primary = f"Coverage (#{rid})"
        sub = resource.get("type", {}).get("text", "Insurance")
    elif rtype == "Organization":
        primary = f"Org: {resource.get('name', rid)}"
        sub = "Healthcare Provider"
    elif rtype == "Practitioner":
        names = resource.get("name", [{}])[0]
        primary = f"Dr. {names.get('family', rid)}"
        sub = "Clinical Attending"
    else:
        primary = f"{rtype} (#{rid})"
        sub = f"Type: {rtype}"

    return primary, sub

def build_fhir_graph(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crawls FHIR Bundle entries, resolves all references recursively,
    and returns nodes and links optimized for ForceGraph2D.
    """
    entries = bundle.get("entry", [])
    nodes = []
    links = []
    node_id_map = {}
    known_ids = set()

    # Step 1: Collect all top-level entry nodes
    for entry in entries:
        res = entry.get("resource", {})
        rid = res.get("id", "")
        rtype = res.get("resourceType", "Resource")
        if not rid:
            continue

        label, sub_label = get_node_label(res)
        
        # Clinical hierarchy weighting for ForceGraph2D
        if rtype == "Patient":
            val = 30
            tier = 0
        elif rtype == "Encounter":
            val = 20
            tier = 1
        elif rtype in ("Condition", "Observation", "MedicationRequest", "Procedure", "Claim"):
            val = 14
            tier = 2
        elif rtype in ("Coverage", "Organization", "Practitioner"):
            val = 12
            tier = 1
        else:
            val = 10
            tier = 3

        node_obj = {
            "id": rid,
            "label": label,
            "subLabel": sub_label,
            "resourceType": rtype,
            "val": val,
            "tier": tier,
            "data": res
        }
        nodes.append(node_obj)
        node_id_map[rid] = node_obj
        known_ids.add(rid)

        # Check for contained resources inside this entry
        for contained in res.get("contained", []):
            cid = contained.get("id", "")
            ctype = contained.get("resourceType", "Resource")
            if cid and cid not in known_ids:
                c_label, c_sub = get_node_label(contained)
                c_node = {
                    "id": cid,
                    "label": f"Contained: {c_label}",
                    "subLabel": c_sub,
                    "resourceType": ctype,
                    "val": 9,
                    "tier": 3,
                    "data": contained
                }
                nodes.append(c_node)
                node_id_map[cid] = c_node
                known_ids.add(cid)

    # Step 2: Extract all references recursively
    link_tracker = set()

    for entry in entries:
        res = entry.get("resource", {})
        source_id = res.get("id", "")
        if not source_id or source_id not in known_ids:
            continue

        # Check contained links
        for contained in res.get("contained", []):
            cid = contained.get("id", "")
            if cid in known_ids:
                pair_key = (source_id, cid, "contains")
                if pair_key not in link_tracker:
                    link_tracker.add(pair_key)
                    links.append({
                        "source": source_id,
                        "target": cid,
                        "relation": "contains"
                    })

        # Recursive scan
        raw_refs = extract_references_recursive(res)
        for relation, raw_target in raw_refs:
            norm_target = normalize_reference(raw_target)
            if not norm_target:
                continue

            # Check if target is a known node ID
            if norm_target in known_ids and norm_target != source_id:
                pair_key = (source_id, norm_target, relation)
                if pair_key not in link_tracker:
                    link_tracker.add(pair_key)
                    links.append({
                        "source": source_id,
                        "target": norm_target,
                        "relation": relation
                    })

    return {
        "nodes": nodes,
        "links": links
    }
