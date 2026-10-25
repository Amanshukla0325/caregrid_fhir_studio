"""
AST Line Mapping, Reference Hovering, Primitive Regex Validation, and Hub Analysis
Inspired by:
1. smart-on-fhir/fred (primitive-validator.coffee, bundle-utils.coffee, ref-warning.cjsx)
2. smart-on-fhir/fhir-viewer (language extension AST line/col mapping, link resolution)

Features:
- Validates FHIR R4 primitive data types using FRED's regex specifications (id, date, dateTime, instant, decimal, etc.).
- Performs recursive reference traversal and inbound/outbound dependency degree & hub analysis (FRED countRefs & _walkNode).
- Maps JSON pointers and reference elements to exact 1-based (line, column) AST coordinates.
- Computes an authoritative 0-100% FHIR R4 Conformance Score across 5 clinical dimensions.
"""

import json
import re
from typing import Dict, Any, List, Tuple, Optional
from utils.json_source_map import parse as parse_json_source_map

# FRED Primitive Regex Validators (from smart-on-fhir/fred: primitive-validator.coffee)
FHIR_PRIMITIVES: Dict[str, Tuple[re.Pattern, str]] = {
    "id": (
        re.compile(r'^[A-Za-z0-9\-\.]{1,64}$'),
        "Upper/lower case ASCII letters ('A'-'Z', 'a'-'z'), numerals ('0'-'9'), '-' and '.', max 64 chars"
    ),
    "date": (
        re.compile(r'^-?[0-9]{4}(-(0[1-9]|1[0-2])(-(0[0-9]|[1-2][0-9]|3[0-1]))?)?$'),
        "ISO 8601 partial or full date (YYYY, YYYY-MM, or YYYY-MM-DD)"
    ),
    "dateTime": (
        re.compile(r'^-?[0-9]{4}(-(0[1-9]|1[0-2])(-(0[0-9]|[1-2][0-9]|3[0-1])(T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]+)?(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?)?)?)?$'),
        "ISO 8601 partial/full date-time with optional timezone"
    ),
    "instant": (
        re.compile(r'^([\+-]?\d{4}(?!\d{2}\b))((-?)((0[1-9]|1[0-2])(\3([12]\d|0[1-9]|3[01]))?|W([0-4]\d|5[0-2])(-?[1-7])?|(00[1-9]|0[1-9]\d|[12]\d{2}|3([0-5]\d|6[1-6])))([T\s]((([01]\d|2[0-3])((:?)[0-5]\d)?|24\:?00)([\.,]\d+(?!:))?)?(\17[0-5]\d([\.,]\d+)?)?([zZ]|([\+-])([01]\d|2[0-3]):?([0-5]\d)?)?)?)?$'),
        "ISO 8601 instant format (e.g. 2024-03-10T14:22:00Z)"
    ),
    "oid": (
        re.compile(r'^urn:oid:[0-2](\.[1-9]\d*)+$'),
        "Object identifier (OID) URI (RFC 3001, e.g. urn:oid:1.2.3.4.5)"
    ),
    "decimal": (
        re.compile(r'^-?\d+(\.\d+)?$'),
        "Signed or unsigned decimal number"
    ),
    "integer": (
        re.compile(r'^-?\d+$'),
        "Signed 32-bit integer"
    ),
    "unsignedInt": (
        re.compile(r'^[0-9]+$'),
        "Non-negative integer (>= 0)"
    ),
    "positiveInt": (
        re.compile(r'^[1-9][0-9]*$'),
        "Positive integer (> 0)"
    ),
    "time": (
        re.compile(r'^([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]+)?$'),
        "Time value (HH:mm:ss)"
    )
}

def validate_primitive(fhir_type: str, value: Any, fail_blank: bool = True) -> Tuple[bool, str]:
    """
    Validates a value against FRED's primitive regex and populating constraints.
    """
    if value is None or value == "":
        return (False, "Value cannot be empty") if fail_blank else (True, "")
    
    val_str = str(value)
    if val_str.startswith(" ") or val_str.endswith(" "):
        return False, "Value cannot begin or end with whitespace"

    if fhir_type in FHIR_PRIMITIVES:
        pattern, desc = FHIR_PRIMITIVES[fhir_type]
        if not pattern.match(val_str):
            return False, f"Expected {fhir_type} ({desc})"

    return True, ""

def generate_json_source_map(json_str: str) -> Dict[str, Dict[str, Any]]:
    """
    Parses JSON using the streaming Poberezkin json-source-map engine
    to map RFC 6901 JSON pointers (/entry/0/resource/status)
    to exact 1-based (line, column) coordinates and character spans.
    """
    try:
        parsed = parse_json_source_map(json_str)
        raw_pointers = parsed.get("pointers", {})
        pointer_map: Dict[str, Dict[str, Any]] = {}

        for ptr, locs in raw_pointers.items():
            key_loc = locs.get("key") or locs.get("value", {})
            val_loc = locs.get("value", {})
            val_end = locs.get("valueEnd", {})

            # 1-based coordinates for UI display
            line_1 = key_loc.get("line", 0) + 1
            col_1 = key_loc.get("column", 0) + 1

            start_pos = val_loc.get("pos", 0)
            end_pos = val_end.get("pos", start_pos)
            preview = json_str[start_pos:min(end_pos, start_pos + 40)].strip()

            pointer_map[ptr] = {
                "line": line_1,
                "col": col_1,
                "pos": key_loc.get("pos", 0),
                "value_pos": start_pos,
                "value_end_pos": end_pos,
                "value_preview": preview,
                "raw_locs": locs
            }
        return pointer_map
    except Exception:
        # Fallback to empty map if invalid JSON
        return {}

def walk_resource_references(node: Any, current_path: str = "") -> List[Dict[str, str]]:
    """
    Recursively traverses any FHIR JSON node to extract all 'reference' fields
    and their property paths (mimicking FRED's _walkNode).
    """
    refs = []
    if isinstance(node, list):
        for i, item in enumerate(node):
            p = f"{current_path}[{i}]" if current_path else f"[{i}]"
            refs.extend(walk_resource_references(item, p))
    elif isinstance(node, dict):
        for k, v in node.items():
            p = f"{current_path}.{k}" if current_path else k
            if k == "reference" and isinstance(v, str) and v:
                refs.append({"path": p, "reference": v.strip()})
            else:
                refs.extend(walk_resource_references(v, p))
    return refs

def analyze_resource_dependencies(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Computes inbound and outbound reference degrees for each resource in the bundle.
    Implements FRED's countRefs() and classifies each resource into its clinical topology:
    - Primary Hub (Inbound >= 2): central anchor referenced by multiple clinical items
    - Bridge (Inbound >= 1 and Outbound >= 1): intermediate clinical pathway node
    - Root Anchor (Inbound >= 1 and Outbound == 0): terminal reference sink
    - Direct Leaf (Inbound == 0 and Outbound >= 1): clinical item referencing an anchor
    - Isolated (0 / 0): standalone resource
    """
    entries = bundle.get("entry", [])
    resources = []
    for idx, e in enumerate(entries):
        res = e.get("resource", {})
        rtype = res.get("resourceType", "Resource")
        rid = res.get("id", "")
        full_url = e.get("fullUrl", "")
        outbound = walk_resource_references(res)
        resources.append({
            "index": idx,
            "resourceType": rtype,
            "id": rid,
            "fullUrl": full_url,
            "resource": res,
            "outbound_refs": outbound,
            "inbound_sources": []
        })

    # Connect inbound references using FRED's reference matching
    for target in resources:
        target_id = target["id"]
        target_type = target["resourceType"]
        target_full = target["fullUrl"]
        
        possible_keys = set()
        if target_id:
            possible_keys.add(target_id.upper())
            possible_keys.add(f"{target_type}/{target_id}".upper())
            possible_keys.add(f"#{target_id}".upper())
            possible_keys.add(f"urn:uuid:{target_id}".upper())
        if target_full:
            possible_keys.add(target_full.upper())

        for source in resources:
            for ref_item in source["outbound_refs"]:
                ref_val = ref_item["reference"].strip().upper()
                uuid_tail = ref_val.replace("URN:UUID:", "")
                slash_tail = ref_val.split("/")[-1] if "/" in ref_val else ref_val
                
                if (ref_val in possible_keys or 
                    uuid_tail in possible_keys or 
                    slash_tail in possible_keys):
                    target["inbound_sources"].append({
                        "sourceType": source["resourceType"],
                        "sourceId": source["id"],
                        "sourcePath": ref_item["path"],
                        "reference": ref_item["reference"]
                    })

    # Build structured dependency summary
    analysis = []
    for r in resources:
        in_deg = len(r["inbound_sources"])
        out_deg = len(r["outbound_refs"])
        
        if in_deg >= 2:
            role = "Primary Hub"
        elif in_deg >= 1 and out_deg >= 1:
            role = "Bridge"
        elif in_deg >= 1 and out_deg == 0:
            role = "Root Anchor"
        elif in_deg == 0 and out_deg >= 1:
            role = "Direct Leaf"
        else:
            role = "Isolated"

        inbound_desc = ", ".join(f"{s['sourceType']} ({s['sourcePath']})" for s in r["inbound_sources"]) if r["inbound_sources"] else "None (0)"
        outbound_desc = ", ".join(f"{o['path']} -> {o['reference']}" for o in r["outbound_refs"]) if r["outbound_refs"] else "None (0)"

        analysis.append({
            "Resource": f"{r['resourceType']} (#{r['id'][:8] if r['id'] else 'anon'})",
            "Resource Type": r["resourceType"],
            "ID": r["id"],
            "Inbound Degree": in_deg,
            "Outbound Degree": out_deg,
            "Topology Role": role,
            "Referenced By": inbound_desc,
            "References Out": outbound_desc,
            "raw_resource": r["resource"],
            "inbound_details": r["inbound_sources"],
            "outbound_details": r["outbound_refs"]
        })

    return analysis

def extract_reference_links(bundle: Dict[str, Any], json_str: str, pointer_map: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Replicates smart-on-fhir/fhir-viewer provideLinks and provideHover:
    Uses Poberezkin's AST source map to locate exact line and column
    for every reference pointer in the bundle and resolves target previews.
    """
    if pointer_map is None:
        pointer_map = generate_json_source_map(json_str)

    references = []
    
    # Pre-index all resources in the bundle by id and fullUrl
    resource_index = {}
    entries = bundle.get("entry", [])
    for e in entries:
        res = e.get("resource", {})
        rid = res.get("id", "")
        full_url = e.get("fullUrl", "")
        rtype = res.get("resourceType", "Resource")
        
        # Display label
        display = rtype
        if rtype == "Patient":
            name = res.get("name", [{}])[0]
            display = f"Patient: {' '.join(name.get('given', []))} {name.get('family', '')}"
        elif rtype == "Practitioner":
            name = res.get("name", [{}])[0]
            display = f"Practitioner: {name.get('text') or name.get('family')}"
        elif rtype == "Organization":
            display = f"Organization: {res.get('name')}"
        elif rtype == "Encounter":
            display = f"Encounter: {res.get('class', {}).get('code', 'Visit')}"
        elif rtype == "Condition":
            display = f"Condition: {res.get('code', {}).get('text') or res.get('id')}"
        elif rtype == "Observation":
            display = f"Observation: {res.get('code', {}).get('text') or res.get('id')}"
        elif rtype == "MedicationRequest":
            display = f"MedicationRequest: {res.get('medicationCodeableConcept', {}).get('text') or res.get('id')}"
        elif rtype == "DocumentReference":
            display = f"DocumentReference: {res.get('description') or res.get('id')}"

        if rid:
            resource_index[rid] = {"type": rtype, "display": display}
            resource_index[f"{rtype}/{rid}"] = {"type": rtype, "display": display}
        if full_url:
            resource_index[full_url] = {"type": rtype, "display": display}

        # Index contained resources
        for cont in res.get("contained", []):
            cid = cont.get("id", "")
            ctype = cont.get("resourceType", "Contained")
            cdisplay = f"Contained: {ctype} (#{cid})"
            if cid:
                resource_index[f"#{cid}"] = {"type": ctype, "display": cdisplay}

    # Extract references from resources and lookup their AST coordinates
    for idx, e in enumerate(entries):
        res = e.get("resource", {})
        rtype = res.get("resourceType", "Resource")
        rid = res.get("id", "")

        outbound = walk_resource_references(res)
        for ref_item in outbound:
            target_ref = ref_item["reference"]
            path_suffix = ref_item["path"].replace(".", "/").replace("[", "/").replace("]", "")
            ptr = f"/entry/{idx}/resource/{path_suffix}"

            # Look up in AST source map
            coords = pointer_map.get(ptr)
            if not coords:
                # Try finding closest matching pointer
                for p_key, c_val in pointer_map.items():
                    if p_key.startswith(f"/entry/{idx}/resource") and p_key.endswith("/reference"):
                        if c_val.get("value_preview", "").strip("\"'") == target_ref:
                            coords = c_val
                            break

            line_num = coords["line"] if coords else 1
            col_num = coords["col"] if coords else 1

            # Resolve target
            resolved = resource_index.get(target_ref)
            if not resolved and target_ref.startswith("urn:uuid:"):
                uuid_tail = target_ref.replace("urn:uuid:", "")
                resolved = resource_index.get(uuid_tail)
            if not resolved and "/" in target_ref:
                tail = target_ref.split("/")[-1]
                resolved = resource_index.get(tail)

            target_type = resolved["type"] if resolved else "External/Unresolved"
            target_display = resolved["display"] if resolved else target_ref

            references.append({
                "Source Resource": f"{rtype} (#{rid[:8]})",
                "Target Reference": target_ref,
                "Target Type": target_type,
                "Target Preview": target_display,
                "Line": line_num,
                "Column": col_num
            })

    return references

def validate_fhir_bundle(bundle: Dict[str, Any], json_str: str = "") -> Dict[str, Any]:
    """
    Validates a FHIR R4 Bundle and computes:
    1. 0 - 100% Conformance Score based on 5 clinical dimensions (including FRED primitive validation).
    2. Detailed Conformance rule breakdown with exact AST (line, col) coordinates.
    3. FRED reference dependency and inbound hub analysis.
    4. Smart-on-FHIR reference link and hover preview table.
    """
    if not json_str:
        json_str = json.dumps(bundle, indent=2)

    pointer_map = generate_json_source_map(json_str)
    references = extract_reference_links(bundle, json_str, pointer_map=pointer_map)
    dependencies = analyze_resource_dependencies(bundle)

    checks = []
    total_points = 0
    earned_points = 0

    def add_check(dimension: str, rule_name: str, passed: bool, weight: int, pointer: str, details: str):
        nonlocal total_points, earned_points
        total_points += weight
        if passed:
            earned_points += weight
        coords = pointer_map.get(pointer, {"line": 1, "col": 1})
        checks.append({
            "Dimension": dimension,
            "Rule Tested": rule_name,
            "Status": "PASS" if passed else "FAIL",
            "JSON Pointer": pointer,
            "Line": coords["line"],
            "Column": coords["col"],
            "Weight": weight,
            "Details": details
        })

    # Dimension 1: Structural Bundle Compliance (20 pts)
    is_bundle = bundle.get("resourceType") == "Bundle"
    add_check("Structure", "Bundle ResourceType", is_bundle, 10, "/resourceType", "Root resourceType is 'Bundle'")

    has_type = bundle.get("type") in ["batch", "collection", "transaction", "document", "history"]
    add_check("Structure", "Bundle Type", has_type, 10, "/type", f"Bundle type is valid '{bundle.get('type')}'")

    entries = bundle.get("entry", [])
    has_entries = len(entries) > 0
    add_check("Structure", "Non-Empty Entry Array", has_entries, 10, "/entry", f"Bundle contains {len(entries)} resources")

    # Dimension 2: Core Mandatory Elements (25 pts)
    for idx, entry in enumerate(entries):
        res = entry.get("resource", {})
        rtype = res.get("resourceType", "Resource")
        rid = res.get("id")

        has_id = bool(rid)
        add_check("Core Elements", f"{rtype}[{idx}] Identifier", has_id, 4, f"/entry/{idx}/resource/id", f"Has identifier id '{rid}'")

        if rtype == "Observation":
            has_status = res.get("status") in ["registered", "preliminary", "final", "amended", "corrected"]
            add_check("Core Elements", f"Observation[{idx}] Status", has_status, 4, f"/entry/{idx}/resource/status", f"Status is '{res.get('status')}'")
            has_code = bool(res.get("code", {}).get("coding")) or bool(res.get("code", {}).get("text"))
            add_check("Core Elements", f"Observation[{idx}] Code", has_code, 4, f"/entry/{idx}/resource/code", "Observation code present")
        elif rtype == "Condition":
            has_clin = bool(res.get("clinicalStatus"))
            add_check("Core Elements", f"Condition[{idx}] ClinicalStatus", has_clin, 4, f"/entry/{idx}/resource/clinicalStatus", "Clinical status present")
            has_diag = bool(res.get("code", {}).get("coding")) or bool(res.get("code", {}).get("text"))
            add_check("Core Elements", f"Condition[{idx}] Diagnosis Code", has_diag, 4, f"/entry/{idx}/resource/code", "Condition diagnostic code present")
        elif rtype == "Encounter":
            has_stat = bool(res.get("status"))
            add_check("Core Elements", f"Encounter[{idx}] Status", has_stat, 4, f"/entry/{idx}/resource/status", f"Status is '{res.get('status')}'")
            has_class = bool(res.get("class"))
            add_check("Core Elements", f"Encounter[{idx}] Class", has_class, 4, f"/entry/{idx}/resource/class", "Encounter class code present")
        elif rtype == "Claim":
            has_tot = bool(res.get("total"))
            add_check("Core Elements", f"Claim[{idx}] Total Charge", has_tot, 4, f"/entry/{idx}/resource/total", "Claim total charge present")
            has_items = len(res.get("item", [])) > 0
            add_check("Core Elements", f"Claim[{idx}] Line Items", has_items, 4, f"/entry/{idx}/resource/item", f"Has {len(res.get('item', []))} service lines")

    # Dimension 3: Terminology Standards Compliance (20 pts)
    has_standard_coding = False
    for entry in entries:
        res = entry.get("resource", {})
        codings = res.get("code", {}).get("coding", [])
        for c in codings:
            system = c.get("system", "")
            if any(s in system for s in ["loinc.org", "icd-10", "snomed.info", "rxnorm", "ama-assn.org"]):
                has_standard_coding = True
                break
    add_check("Terminology", "Standard Vocabulary URIs", has_standard_coding, 20, "/entry", "Codes bound to standard LOINC/ICD-10/SNOMED/CPT systems")

    # Dimension 4: Reference Integrity & Centrality (20 pts)
    dangling_refs = [r for r in references if r["Target Type"] == "External/Unresolved"]
    all_refs_valid = len(dangling_refs) == 0
    add_check("Integrity", "Reference Resolution", all_refs_valid, 20, "/entry", f"All {len(references)} references resolve to resources within the bundle")

    # Dimension 5: FRED Primitive Regex Conformance (15 pts)
    for idx, entry in enumerate(entries):
        res = entry.get("resource", {})
        rtype = res.get("resourceType", "Resource")
        rid = res.get("id")

        if rid:
            valid_id, id_msg = validate_primitive("id", rid)
            add_check(
                "FRED Primitives",
                f"{rtype}[{idx}].id Format",
                valid_id,
                2,
                f"/entry/{idx}/resource/id",
                "Regex matches FRED ^[A-Za-z0-9\\-\\.]{1,64}$" if valid_id else id_msg
            )

        if "birthDate" in res:
            bdate = res.get("birthDate")
            valid_d, d_msg = validate_primitive("date", bdate)
            add_check(
                "FRED Primitives",
                f"{rtype}[{idx}].birthDate Format",
                valid_d,
                2,
                f"/entry/{idx}/resource/birthDate",
                f"ISO 8601 date '{bdate}' matches FRED date specification" if valid_d else d_msg
            )

        for dt_field in ["effectiveDateTime", "authoredOn", "created", "date"]:
            if dt_field in res:
                dt_val = res.get(dt_field)
                valid_dt, dt_msg = validate_primitive("dateTime", dt_val)
                add_check(
                    "FRED Primitives",
                    f"{rtype}[{idx}].{dt_field} Format",
                    valid_dt,
                    2,
                    f"/entry/{idx}/resource/{dt_field}",
                    f"ISO 8601 dateTime '{dt_val}' matches FRED dateTime specification" if valid_dt else dt_msg
                )

    conformance_score = round((earned_points / max(total_points, 1)) * 100)

    return {
        "conformance_score": conformance_score,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["Status"] == "PASS"),
        "failed_checks": sum(1 for c in checks if c["Status"] == "FAIL"),
        "checks": checks,
        "references": references,
        "dependencies": dependencies,
        "pointer_map": pointer_map
    }
