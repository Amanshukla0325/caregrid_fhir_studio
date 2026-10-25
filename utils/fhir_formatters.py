"""
Medplum-Style Clinical Formatters & Encounter Timeline Builder
Directly adapted from @medplum/core (src/format.ts) and @medplum/react (src/ResourcePropertyDisplay/, src/Timeline/):

Utilities:
- format_human_name: normalizes prefix, given[], family, suffix, [use]
- format_address: line, city, state, postalCode, country
- format_codeable_concept: text first, falling back to Display (Code)
- format_coding: display (code)
- format_quantity: comparator, value, unit
- format_observation_value: handles valueQuantity, valueCodeableConcept, valueString, and component[]
- format_period: start - end
- build_encounter_timeline: organizes loose FHIR bundles chronologically by encounter
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

def ensure_str(val: Any) -> Optional[str]:
    return str(val) if isinstance(val, (str, int, float)) and val != "" else None

def format_human_name(name: Optional[Dict[str, Any]]) -> str:
    """Adapted from Medplum formatHumanName (format.ts)"""
    if not name or not isinstance(name, dict):
        return ""

    builder = []
    prefix = name.get("prefix")
    if prefix:
        if isinstance(prefix, list):
            builder.extend(p for p in prefix if p)
        elif isinstance(prefix, str):
            builder.append(prefix)

    given = name.get("given")
    if given:
        if isinstance(given, list):
            builder.extend(g for g in given if g)
        elif isinstance(given, str):
            builder.append(given)

    family = name.get("family")
    if family:
        builder.append(str(family))

    suffix = name.get("suffix")
    if suffix:
        if isinstance(suffix, list):
            builder.extend(s for s in suffix if s)
        elif isinstance(suffix, str):
            builder.append(suffix)

    if not builder and name.get("text"):
        return str(name["text"])

    return " ".join(builder).strip()

def format_address(addr: Optional[Dict[str, Any]]) -> str:
    """Adapted from Medplum formatAddress (format.ts)"""
    if not addr or not isinstance(addr, dict):
        return ""

    parts = []
    lines = addr.get("line")
    if lines:
        if isinstance(lines, list):
            parts.extend(l for l in lines if l)
        elif isinstance(lines, str):
            parts.append(lines)

    city_state_zip = []
    if addr.get("city"):
        city_state_zip.append(str(addr["city"]))
    if addr.get("state"):
        city_state_zip.append(str(addr["state"]))
    if addr.get("postalCode"):
        city_state_zip.append(str(addr["postalCode"]))

    if city_state_zip:
        parts.append(", ".join(city_state_zip))

    if addr.get("country"):
        parts.append(str(addr["country"]))

    return ", ".join(parts).strip()

def format_coding(coding: Optional[Dict[str, Any]], include_code: bool = True) -> str:
    """Adapted from Medplum formatCoding (format.ts)"""
    if not coding or not isinstance(coding, dict):
        return ""

    display = ensure_str(coding.get("display"))
    code = ensure_str(coding.get("code"))

    if display:
        return f"{display} ({code})" if include_code and code else display
    return code or ""

def format_codeable_concept(cc: Optional[Dict[str, Any]]) -> str:
    """Adapted from Medplum formatCodeableConcept (format.ts)"""
    if not cc or not isinstance(cc, dict):
        return ""

    text = ensure_str(cc.get("text"))
    if text:
        return text

    codings = cc.get("coding")
    if codings and isinstance(codings, list):
        return ", ".join(format_coding(c) for c in codings if c)
    return ""

def format_quantity(q: Optional[Dict[str, Any]], precision: Optional[int] = None) -> str:
    """Adapted from Medplum formatQuantity (format.ts)"""
    if not q or not isinstance(q, dict):
        return ""

    parts = []
    if q.get("comparator"):
        parts.append(str(q["comparator"]))

    val = q.get("value")
    if val is not None:
        if precision is not None and isinstance(val, (int, float)):
            parts.append(f"{val:.{precision}f}")
        else:
            parts.append(str(val))

    unit = ensure_str(q.get("unit"))
    if unit:
        if parts and unit != "%":
            parts.append(f" {unit}")
        else:
            parts.append(unit)

    return "".join(parts).strip()

def format_observation_value(obs: Optional[Dict[str, Any]]) -> str:
    """Adapted from Medplum formatObservationValue (format.ts)"""
    if not obs or not isinstance(obs, dict):
        return ""

    if "valueQuantity" in obs:
        return format_quantity(obs["valueQuantity"])
    elif "valueCodeableConcept" in obs:
        return format_codeable_concept(obs["valueCodeableConcept"])
    elif "valueString" in obs:
        return str(obs["valueString"])
    elif "component" in obs and isinstance(obs["component"], list):
        comp_parts = []
        for c in obs["component"]:
            c_code = format_codeable_concept(c.get("code"))
            c_val = format_observation_value(c)
            if c_code and c_val:
                comp_parts.append(f"{c_code}: {c_val}")
            elif c_val:
                comp_parts.append(c_val)
        return " / ".join(comp_parts)

    return ""

def format_period(p: Optional[Dict[str, Any]]) -> str:
    """Adapted from Medplum formatPeriod (format.ts)"""
    if not p or not isinstance(p, dict):
        return ""

    start = ensure_str(p.get("start")) or ""
    end = ensure_str(p.get("end")) or ""

    if start and end:
        return f"{start[:10]} - {end[:10]}"
    return start[:10] if start else (end[:10] if end else "")

def get_clinical_event_time(resource: Dict[str, Any]) -> str:
    """
    Extracts the true clinical event timestamp.
    Adapted from Medplum sortByDateAndPriority (date.ts).
    """
    rtype = resource.get("resourceType", "")

    if rtype == "Observation":
        return str(resource.get("effectiveDateTime") or resource.get("issued") or resource.get("meta", {}).get("lastUpdated") or "1970-01-01")
    elif rtype == "DiagnosticReport":
        return str(resource.get("issued") or resource.get("effectiveDateTime") or "1970-01-01")
    elif rtype == "Condition":
        return str(resource.get("onsetDateTime") or resource.get("recordedDate") or "1970-01-01")
    elif rtype == "MedicationRequest":
        return str(resource.get("authoredOn") or "1970-01-01")
    elif rtype == "Encounter":
        p = resource.get("period", {})
        return str(p.get("start") or "1970-01-01")
    elif rtype == "Procedure":
        return str(resource.get("performedDateTime") or "1970-01-01")
    elif rtype == "Claim":
        return str(resource.get("created") or "1970-01-01")

    return str(resource.get("meta", {}).get("lastUpdated") or "1970-01-01")

def build_clinical_summary(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds a high-level clinical summary of the bundle for Medplum-style display:
    1. Patient Demographics Banner
    2. Encounters with nested Clinical Items (Conditions, Labs, Meds, Procedures)
    3. Standalone / Historical Records
    """
    entries = bundle.get("entry", [])
    patient = None
    encounters = []
    clinical_items = []

    for e in entries:
        res = e.get("resource", {})
        rtype = res.get("resourceType")
        if rtype == "Patient" and not patient:
            patient = res
        elif rtype == "Encounter":
            encounters.append(res)
        elif rtype in ("Condition", "Observation", "MedicationRequest", "Procedure", "Claim", "AllergyIntolerance"):
            clinical_items.append(res)

    # Patient info
    patient_name = "Anonymous Patient"
    patient_gender = "Unknown"
    patient_dob = "Unknown"
    patient_mrn = "N/A"

    if patient:
        names = patient.get("name", [])
        if names:
            patient_name = format_human_name(names[0])
        patient_gender = (patient.get("gender") or "Unknown").capitalize()
        patient_dob = patient.get("birthDate") or "Unknown"

        identifiers = patient.get("identifier", [])
        if identifiers:
            patient_mrn = identifiers[0].get("value") or "N/A"

    # Group clinical items under encounters if referenced
    encounter_cards = []
    unattached_items = []

    # Map encounter IDs
    enc_map = {enc.get("id"): [] for enc in encounters if enc.get("id")}

    for item in clinical_items:
        enc_ref = item.get("encounter", {}).get("reference", "")
        # Check if reference points to an encounter in enc_map
        matched = False
        for eid in enc_map:
            if eid in enc_ref:
                enc_map[eid].append(item)
                matched = True
                break
        if not matched:
            unattached_items.append(item)

    for enc in encounters:
        eid = enc.get("id", "")
        items = enc_map.get(eid, [])
        # Sort items chronologically (Medplum sortByDateAndPriority)
        items.sort(key=lambda r: get_clinical_event_time(r), reverse=True)

        enc_class = enc.get("class", {})
        class_display = enc_class.get("display") or enc_class.get("code") or "Clinical Encounter"
        period_str = format_period(enc.get("period")) or enc.get("period", {}).get("start", "")[:10]

        encounter_cards.append({
            "id": eid,
            "title": f"Encounter: {class_display}",
            "period": period_str,
            "status": (enc.get("status") or "completed").capitalize(),
            "items": [format_clinical_item(it) for it in items]
        })

    # Also format unattached clinical items
    unattached_items.sort(key=lambda r: get_clinical_event_time(r), reverse=True)
    other_records = [format_clinical_item(it) for it in unattached_items]

    return {
        "patient": {
            "name": patient_name,
            "gender": patient_gender,
            "dob": patient_dob,
            "mrn": patient_mrn
        },
        "encounters": encounter_cards,
        "other_records": other_records
    }

def format_clinical_item(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Formats an individual clinical resource into a clean Medplum display card"""
    rtype = resource.get("resourceType", "Resource")
    rid = resource.get("id", "")[:8]
    raw_date = get_clinical_event_time(resource)
    date_str = raw_date[:10] if raw_date and not raw_date.startswith("1970") else "—"

    title = rtype
    detail = ""
    status = resource.get("status") or ""

    if rtype == "Condition":
        title = format_codeable_concept(resource.get("code")) or "Condition"
        clin_stat = resource.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "active")
        ver_stat = resource.get("verificationStatus", {}).get("coding", [{}])[0].get("code", "confirmed")
        detail = f"Status: {clin_stat.capitalize()} ({ver_stat})"
        status = clin_stat
    elif rtype == "Observation":
        title = format_codeable_concept(resource.get("code")) or "Lab / Observation"
        obs_val = format_observation_value(resource)
        interp = resource.get("interpretation", [{}])[0].get("coding", [{}])[0].get("code")
        flag = f" [{interp}]" if interp else ""
        detail = f"Value: {obs_val}{flag}"
    elif rtype == "MedicationRequest":
        med_cc = resource.get("medicationCodeableConcept")
        if med_cc:
            title = format_codeable_concept(med_cc)
        elif "medicationReference" in resource:
            med_ref = resource.get("medicationReference", {})
            title = med_ref.get("display") or med_ref.get("reference") or "Medication"
        else:
            title = "Medication"
        dosages = resource.get("dosageInstruction", [])
        dose_text = dosages[0].get("text") if dosages else "As directed"
        detail = f"Dose: {dose_text}"
    elif rtype == "AllergyIntolerance":
        title = format_codeable_concept(resource.get("code")) or "Allergy"
        cat = ", ".join(resource.get("category", ["medication"]))
        detail = f"Category: {cat.capitalize()}"
    elif rtype == "Procedure":
        title = format_codeable_concept(resource.get("code")) or "Procedure"
        detail = f"Status: {status.capitalize()}"
    elif rtype == "Claim":
        tot = resource.get("total", {})
        val = tot.get("value", 0.0)
        curr = tot.get("currency", "USD")
        items = len(resource.get("item", []))
        title = f"Medical Claim (#{resource.get('id', '')[:8]})"
        detail = f"Total Charge: ${val:.2f} {curr} | {items} service lines"

    return {
        "resourceType": rtype,
        "id": rid,
        "title": title,
        "detail": detail,
        "status": status.capitalize() if status else "Active",
        "date": date_str,
        "raw": resource
    }
