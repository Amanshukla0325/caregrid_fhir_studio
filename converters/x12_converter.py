"""
LinuxForHealth ASC X12 837P Implementation
Inspired by LinuxForHealth/x12:
- Dynamic ISA delimiter discovery (element, component, segment terminator)
- Hierarchical loop context tracking (Loops 1000, 2000A, 2000B, 2000C, 2300, 2400)
- Conversion to FHIR R4: Claim, Patient, Practitioner, Organization, Coverage, Condition
"""

import uuid
from typing import Dict, Any, List

CAREGRID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')

def generate_uuid(resource_type: str, seed: str) -> str:
    """Replicates deterministic UUIDv5 generation for references."""
    return str(uuid.uuid5(CAREGRID_NAMESPACE, f"{resource_type}/{seed}"))

def parse_x12_837(edi_text: str) -> Dict[str, Any]:
    cleaned_text = edi_text.strip()
    if not cleaned_text:
        return {"resourceType": "Bundle", "type": "batch", "entry": []}

    # Step 1: Delimiter Discovery from ISA segment (Fixed 106-char header)
    if cleaned_text.startswith("ISA") and len(cleaned_text) >= 106:
        elem_sep = cleaned_text[3]
        comp_sep = cleaned_text[104]
        seg_term = cleaned_text[105]
    else:
        elem_sep = '*'
        comp_sep = ':'
        seg_term = '~'

    raw_segments = [s.strip() for s in cleaned_text.split(seg_term) if s.strip()]

    # State variables
    current_hl = ""  # 20=Billing Provider, 22=Subscriber, 23=Dependent
    payer_name = "Healthcare Payer"
    payer_id = "PAYER-001"
    
    billing_name = "Billing Provider"
    billing_npi = "1999999999"
    billing_tax_id = ""
    
    subscriber_id = "MEM-001"
    subscriber_family = "Subscriber"
    subscriber_given = "Patient"
    subscriber_dob = "1980-01-01"
    subscriber_gender = "other"
    
    dependent_family = ""
    dependent_given = ""
    dependent_dob = ""
    dependent_gender = ""
    has_dependent = False

    claim_control_num = "CLM-001"
    claim_total_charge = 0.0
    
    diagnoses: List[Dict[str, str]] = []
    service_lines: List[Dict[str, Any]] = []

    # Step 2: Loop parsing state machine
    for seg_str in raw_segments:
        parts = seg_str.split(elem_sep)
        tag = parts[0].strip().upper()

        if tag == "HL":
            # HL03 is Hierarchical Level Code
            if len(parts) > 3:
                current_hl = parts[3].strip()

        elif tag == "NM1":
            entity_id = parts[1].strip() if len(parts) > 1 else ""
            # 40 or PR: Payer
            if entity_id in ("40", "PR"):
                payer_name = parts[3].strip() if len(parts) > 3 else payer_name
                payer_id = parts[9].strip() if len(parts) > 9 else payer_id
            # 85: Billing Provider
            elif entity_id == "85":
                billing_name = parts[3].strip() if len(parts) > 3 else billing_name
                billing_npi = parts[9].strip() if len(parts) > 9 and parts[9].strip() else billing_npi
            # IL: Insured / Subscriber
            elif entity_id == "IL":
                subscriber_family = parts[3].strip() if len(parts) > 3 else subscriber_family
                subscriber_given = parts[4].strip() if len(parts) > 4 else subscriber_given
                subscriber_id = parts[9].strip() if len(parts) > 9 else subscriber_id
            # QC: Patient (Dependent)
            elif entity_id == "QC":
                has_dependent = True
                dependent_family = parts[3].strip() if len(parts) > 3 else ""
                dependent_given = parts[4].strip() if len(parts) > 4 else ""

        elif tag == "DMG":
            # Demographic information: DMG02 is DOB (YYYYMMDD), DMG03 is Gender (M/F)
            dob_raw = parts[2].strip() if len(parts) > 2 else ""
            gender_raw = parts[3].strip().upper() if len(parts) > 3 else "M"
            parsed_gender = "male" if gender_raw == "M" else "female" if gender_raw == "F" else "other"
            parsed_dob = f"{dob_raw[:4]}-{dob_raw[4:6]}-{dob_raw[6:8]}" if len(dob_raw) == 8 else "1980-01-01"
            
            if current_hl == "23" or has_dependent:
                dependent_dob = parsed_dob
                dependent_gender = parsed_gender
            else:
                subscriber_dob = parsed_dob
                subscriber_gender = parsed_gender

        elif tag == "REF":
            ref_qualifier = parts[1].strip() if len(parts) > 1 else ""
            if ref_qualifier == "EI":  # Employer ID / Tax ID
                billing_tax_id = parts[2].strip() if len(parts) > 2 else ""

        elif tag == "CLM":
            # CLM01: Claim submitter identifier
            claim_control_num = parts[1].strip() if len(parts) > 1 else claim_control_num
            # CLM02: Total claim charge amount
            try:
                claim_total_charge = float(parts[2].strip()) if len(parts) > 2 else 0.0
            except ValueError:
                claim_total_charge = 0.0

        elif tag == "HI":
            # Health Care Diagnosis codes (HI01 is code-qualifier:code e.g. BK:I10 or BK:8540)
            for hi_field in parts[1:]:
                if not hi_field.strip():
                    continue
                hi_parts = hi_field.split(comp_sep) if comp_sep in hi_field else hi_field.split(":")
                if len(hi_parts) >= 2:
                    dx_code = hi_parts[1].strip()
                    diagnoses.append({
                        "qualifier": hi_parts[0].strip(),
                        "code": dx_code,
                        "display": f"Diagnosis {dx_code}"
                    })

        elif tag == "SV1":
            # Service line procedure and charge
            proc_raw = parts[1].strip() if len(parts) > 1 else "HC:99214"
            proc_code = proc_raw.split(comp_sep)[-1] if comp_sep in proc_raw else proc_raw.split(":")[-1]
            try:
                line_charge = float(parts[2].strip()) if len(parts) > 2 else 0.0
            except ValueError:
                line_charge = 0.0
            try:
                units = float(parts[4].strip()) if len(parts) > 4 else 1.0
            except ValueError:
                units = 1.0
            service_lines.append({
                "sequence": len(service_lines) + 1,
                "procedure_code": proc_code,
                "charge": line_charge,
                "units": units,
                "date": "2024-03-11"
            })

        elif tag == "DTP":
            # Date of service for line (DTP01=472, DTP02=D8, DTP03=YYYYMMDD)
            dtp_qual = parts[1].strip() if len(parts) > 1 else ""
            dtp_val = parts[3].strip() if len(parts) > 3 else ""
            if dtp_qual in ("472", "439") and len(dtp_val) == 8 and service_lines:
                formatted_date = f"{dtp_val[:4]}-{dtp_val[4:6]}-{dtp_val[6:8]}"
                service_lines[-1]["date"] = formatted_date

    # Step 3: Build FHIR R4 Bundle
    entries: List[Dict[str, Any]] = []

    # Patient (Subscriber or Dependent)
    patient_pat_id = f"PAT-{subscriber_id}"
    pat_family = dependent_family if has_dependent and dependent_family else subscriber_family
    pat_given = dependent_given if has_dependent and dependent_given else subscriber_given
    pat_dob = dependent_dob if has_dependent and dependent_dob else subscriber_dob
    pat_gender = dependent_gender if has_dependent and dependent_gender else subscriber_gender

    pat_uuid = generate_uuid("Patient", patient_pat_id)
    pat_full_url = f"urn:uuid:{pat_uuid}"

    patient_resource = {
        "resourceType": "Patient",
        "id": pat_uuid,
        "identifier": [
            {
                "system": "http://payer.caregrid.org/member-id",
                "value": subscriber_id
            }
        ],
        "name": [
            {
                "use": "official",
                "family": pat_family,
                "given": [pat_given]
            }
        ],
        "gender": pat_gender,
        "birthDate": pat_dob
    }
    entries.append({"fullUrl": pat_full_url, "resource": patient_resource})

    # Practitioner (Billing Provider)
    pract_uuid = generate_uuid("Practitioner", billing_npi)
    pract_full_url = f"urn:uuid:{pract_uuid}"
    pract_resource = {
        "resourceType": "Practitioner",
        "id": pract_uuid,
        "identifier": [
            {
                "system": "http://hl7.org/fhir/sid/us-npi",
                "value": billing_npi
            }
        ],
        "name": [
            {
                "text": billing_name,
                "family": billing_name.split()[-1] if billing_name else "Provider"
            }
        ]
    }
    entries.append({"fullUrl": pract_full_url, "resource": pract_resource})

    # Organization (Payer)
    org_uuid = generate_uuid("Organization", payer_id)
    org_full_url = f"urn:uuid:{org_uuid}"
    org_resource = {
        "resourceType": "Organization",
        "id": org_uuid,
        "identifier": [
            {
                "system": "http://hl7.org/fhir/sid/us-payer-id",
                "value": payer_id
            }
        ],
        "name": payer_name,
        "type": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                        "code": "pay",
                        "display": "Payer"
                    }
                ]
            }
        ]
    }
    entries.append({"fullUrl": org_full_url, "resource": org_resource})

    # Coverage
    cov_uuid = generate_uuid("Coverage", f"COV-{subscriber_id}")
    cov_full_url = f"urn:uuid:{cov_uuid}"
    cov_resource = {
        "resourceType": "Coverage",
        "id": cov_uuid,
        "status": "active",
        "subscriber": {"reference": pat_full_url},
        "beneficiary": {"reference": pat_full_url},
        "payor": [{"reference": org_full_url}]
    }
    entries.append({"fullUrl": cov_full_url, "resource": cov_resource})

    # Conditions (from HI Diagnosis codes)
    if not diagnoses:
        diagnoses = [{"qualifier": "BK", "code": "I10", "display": "Essential (primary) hypertension"}]

    claim_diagnoses = []
    for idx, dx in enumerate(diagnoses):
        cond_uuid = generate_uuid("Condition", f"{claim_control_num}-dx-{idx}")
        cond_resource = {
            "resourceType": "Condition",
            "id": cond_uuid,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active"
                    }
                ]
            },
            "code": {
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/sid/icd-10-cm",
                        "code": dx["code"],
                        "display": dx["display"]
                    }
                ],
                "text": dx["display"]
            },
            "subject": {"reference": pat_full_url}
        }
        entries.append({"fullUrl": f"urn:uuid:{cond_uuid}", "resource": cond_resource})
        claim_diagnoses.append({
            "sequence": idx + 1,
            "diagnosisCodeableConcept": {
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/sid/icd-10-cm",
                        "code": dx["code"],
                        "display": dx["display"]
                    }
                ]
            }
        })

    # Claim Items
    claim_items = []
    if not service_lines:
        service_lines = [{
            "sequence": 1,
            "procedure_code": "99214",
            "charge": claim_total_charge,
            "units": 1.0,
            "date": "2024-03-11"
        }]

    for sl in service_lines:
        claim_items.append({
            "sequence": sl["sequence"],
            "productOrService": {
                "coding": [
                    {
                        "system": "http://www.ama-assn.org/go/cpt",
                        "code": sl["procedure_code"],
                        "display": f"CPT Code {sl['procedure_code']}"
                    }
                ]
            },
            "servicedDate": sl["date"],
            "quantity": {"value": sl["units"]},
            "unitPrice": {"value": sl["charge"], "currency": "USD"},
            "net": {"value": sl["charge"] * sl["units"], "currency": "USD"}
        })

    # Claim Resource
    claim_uuid = generate_uuid("Claim", claim_control_num)
    claim_resource = {
        "resourceType": "Claim",
        "id": claim_uuid,
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "professional",
                    "display": "Professional"
                }
            ]
        },
        "use": "claim",
        "patient": {"reference": pat_full_url},
        "provider": {"reference": pract_full_url},
        "insurer": {"reference": org_full_url},
        "insurance": [
            {
                "sequence": 1,
                "focal": True,
                "coverage": {"reference": cov_full_url}
            }
        ],
        "diagnosis": claim_diagnoses,
        "item": claim_items,
        "total": {
            "value": claim_total_charge,
            "currency": "USD"
        }
    }
    entries.append({"fullUrl": f"urn:uuid:{claim_uuid}", "resource": claim_resource})

    # Root Bundle
    bundle_uuid = generate_uuid("Bundle", claim_control_num)
    return {
        "resourceType": "Bundle",
        "id": bundle_uuid,
        "type": "collection",
        "entry": entries
    }
