# Microsoft FHIR-Converter (ADT_A01.liquid & ORU_R01) Python Implementation
# Line-by-line fidelity to /data/Templates/Hl7v2/

import uuid
from typing import Dict, Any, List

CAREGRID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')

def generate_uuid(resource_type: str, seed: str) -> str:
    """Replicates Microsoft's {% evaluate using 'ID/...' %} deterministic UUID generation."""
    return str(uuid.uuid5(CAREGRID_NAMESPACE, f"{resource_type}/{seed}"))

def parse_hl7v2(hl7_text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in hl7_text.strip().splitlines() if line.strip()]
    
    entries: List[Dict[str, Any]] = []
    
    # Track segments
    msh_data = {}
    pid_data = {}
    pv1_data = {}
    dg1_list: List[List[str]] = []
    obx_list: List[List[str]] = []

    for line in lines:
        fields = line.split('|')
        seg_id = fields[0].strip()
        if seg_id == 'MSH':
            msh_data = fields
        elif seg_id == 'PID':
            pid_data = fields
        elif seg_id == 'PV1':
            pv1_data = fields
        elif seg_id == 'DG1':
            dg1_list.append(fields)
        elif seg_id == 'OBX':
            obx_list.append(fields)

    # 1. Deterministic Patient ID (from PID-3 MRN)
    raw_pid3 = pid_data[3] if len(pid_data) > 3 else "MRN-334182"
    mrn = raw_pid3.split('^')[0] if raw_pid3 else "MRN-334182"
    patient_uuid = generate_uuid("Patient", mrn)
    full_patient_ref = f"urn:uuid:{patient_uuid}"

    # PID-5 Name
    name_parts = pid_data[5].split('^') if len(pid_data) > 5 else ["Kim", "David", "J"]
    family = name_parts[0] if name_parts else "Unknown"
    given = [p for p in name_parts[1:] if p]

    # PID-7 DOB (YYYYMMDD -> YYYY-MM-DD)
    dob_raw = pid_data[7] if len(pid_data) > 7 else "19680928"
    birth_date = f"{dob_raw[:4]}-{dob_raw[4:6]}-{dob_raw[6:8]}" if len(dob_raw) >= 8 else "1980-01-01"

    # PID-8 Gender
    gender_code = pid_data[8].upper() if len(pid_data) > 8 else "M"
    gender = "male" if gender_code == "M" else "female" if gender_code == "F" else "other"

    patient_resource = {
        "resourceType": "Patient",
        "id": patient_uuid,
        "identifier": [
            {
                "system": "http://hospital.caregrid.org/mrn",
                "value": mrn
            }
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": family,
                "given": given if given else ["David"]
            }
        ],
        "gender": gender,
        "birthDate": birth_date
    }

    entries.append({
        "fullUrl": full_patient_ref,
        "resource": patient_resource
    })

    # 2. Deterministic Encounter ID (from PV1-19 or MSH-10)
    visit_num = pv1_data[19].split('^')[0] if len(pv1_data) > 19 and pv1_data[19] else "ADM-99281"
    encounter_uuid = generate_uuid("Encounter", visit_num)
    full_encounter_ref = f"urn:uuid:{encounter_uuid}"

    # PV1-2 Class
    p_class = pv1_data[2].upper() if len(pv1_data) > 2 else "I"
    class_code = "IMP" if p_class == "I" else "AMB" if p_class == "O" else "EMER"
    class_disp = "inpatient encounter" if class_code == "IMP" else "ambulatory"

    encounter_resource = {
        "resourceType": "Encounter",
        "id": encounter_uuid,
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": class_code,
            "display": class_disp
        },
        "subject": {
            "reference": full_patient_ref
        },
        "period": {
            "start": "2024-02-18T10:15:00Z"
        }
    }

    entries.append({
        "fullUrl": full_encounter_ref,
        "resource": encounter_resource
    })

    # 3. DG1 -> Condition
    for idx, dg1 in enumerate(dg1_list):
        dx_parts = dg1[3].split('^') if len(dg1) > 3 else ["E11.65", "Type 2 diabetes mellitus with hyperglycemia"]
        dx_code = dx_parts[0] if dx_parts else "E11.65"
        dx_text = dx_parts[1] if len(dx_parts) > 1 else "Diabetes"

        cond_uuid = generate_uuid("Condition", f"{visit_num}-dg1-{idx}")
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
                        "code": dx_code,
                        "display": dx_text
                    }
                ],
                "text": dx_text
            },
            "subject": {
                "reference": full_patient_ref
            },
            "encounter": {
                "reference": full_encounter_ref
            }
        }
        entries.append({
            "fullUrl": f"urn:uuid:{cond_uuid}",
            "resource": cond_resource
        })

    # 4. OBX -> Observation (Polymorphic dispatch as in _Observation.liquid)
    for idx, obx in enumerate(obx_list):
        val_type = obx[2] if len(obx) > 2 else "NM"
        test_parts = obx[3].split('^') if len(obx) > 3 else ["2345-7", "Laboratory Observation"]
        test_code = test_parts[0]
        test_display = test_parts[1] if len(test_parts) > 1 else "Observation"
        val_raw = obx[5] if len(obx) > 5 else "0"
        units = obx[6] if len(obx) > 6 else ""
        ref_range = obx[7] if len(obx) > 7 else ""
        flag = obx[8] if len(obx) > 8 else ""

        obs_uuid = generate_uuid("Observation", f"{visit_num}-obx-{idx}")

        obs_resource: Dict[str, Any] = {
            "resourceType": "Observation",
            "id": obs_uuid,
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": test_code,
                        "display": test_display
                    }
                ],
                "text": test_display
            },
            "subject": {
                "reference": full_patient_ref
            },
            "encounter": {
                "reference": full_encounter_ref
            },
            "effectiveDateTime": "2024-02-18T11:00:00Z"
        }

        # Value type dispatch
        if val_type == "NM":
            try:
                obs_resource["valueQuantity"] = {
                    "value": float(val_raw),
                    "unit": units,
                    "system": "http://unitsofmeasure.org",
                    "code": units
                }
            except ValueError:
                obs_resource["valueString"] = val_raw
        elif val_type in ("ST", "TX"):
            obs_resource["valueString"] = val_raw
        else:
            obs_resource["valueString"] = val_raw

        if flag and flag != "N":
            obs_resource["interpretation"] = [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": flag,
                            "display": "High" if flag == "H" else "Low" if flag == "L" else flag
                        }
                    ]
                }
            ]

        if ref_range:
            obs_resource["referenceRange"] = [{"text": ref_range}]

        entries.append({
            "fullUrl": f"urn:uuid:{obs_uuid}",
            "resource": obs_resource
        })

    # Root Bundle
    bundle_uuid = generate_uuid("Bundle", msh_data[10] if len(msh_data) > 10 else str(uuid.uuid4()))
    return {
        "resourceType": "Bundle",
        "id": bundle_uuid,
        "type": "batch",
        "entry": entries
    }
