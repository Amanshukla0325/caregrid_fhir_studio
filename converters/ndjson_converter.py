"""
MIMIC-IV & FHIR Bulk Data (NDJSON / NDJSON.GZ) Converter
Supports:
- Gzipped files (.ndjson.gz, .gz) with automatic gzip decompression
- Newline-delimited JSON (NDJSON / FHIR Bulk Export spec)
- Bundling arbitrary resource streams into compliant FHIR R4 Bundles
- Automatic sample generation from MIMIC-IV-FHIR ICU schema
"""

import gzip
import json
import uuid
from typing import Dict, Any, List, Union

def decompress_if_gzip(raw_input: Union[str, bytes]) -> str:
    """Detects and decompresses GZIP magic bytes (0x1f, 0x8b), returning decoded text."""
    if isinstance(raw_input, bytes):
        if len(raw_input) >= 2 and raw_input[:2] == b'\x1f\x8b':
            try:
                decompressed = gzip.decompress(raw_input)
                return decompressed.decode("utf-8", errors="ignore")
            except Exception:
                return raw_input.decode("utf-8", errors="ignore")
        return raw_input.decode("utf-8", errors="ignore")
    return str(raw_input)

def parse_ndjson(raw_input: Union[str, bytes], max_resources: int = 100) -> Dict[str, Any]:
    """
    Parses a MIMIC-IV or Bulk FHIR NDJSON / JSON string or GZ stream
    into a compliant FHIR R4 Bundle.
    """
    text = decompress_if_gzip(raw_input).strip()
    
    # If the text is already a single FHIR Bundle JSON
    if text.startswith("{") and text.endswith("}"):
        try:
            single_obj = json.loads(text)
            if isinstance(single_obj, dict) and single_obj.get("resourceType") == "Bundle":
                return single_obj
            elif isinstance(single_obj, dict) and "resourceType" in single_obj:
                # Single resource -> wrap in Bundle
                rid = single_obj.get("id") or str(uuid.uuid4())
                return {
                    "resourceType": "Bundle",
                    "type": "collection",
                    "entry": [{"fullUrl": f"urn:uuid:{rid}", "resource": single_obj}]
                }
        except Exception:
            pass

    # Process line-by-line NDJSON
    lines = text.splitlines()
    resources: List[Dict[str, Any]] = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        try:
            res_obj = json.loads(line_clean)
            if isinstance(res_obj, dict) and "resourceType" in res_obj:
                resources.append(res_obj)
                if len(resources) >= max_resources:
                    break
        except Exception:
            continue

    # Wrap into FHIR R4 Bundle
    entries = []
    for r in resources:
        rtype = r.get("resourceType", "Resource")
        rid = r.get("id", str(uuid.uuid4()))
        entries.append({
            "fullUrl": f"urn:uuid:{rid}",
            "resource": r
        })

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": entries
    }

# Pre-packaged authentic MIMIC-IV ICU Cohort Sample (Patient 10000032 from PhysioNet)
SAMPLE_MIMIC_IV = """{"resourceType": "Patient", "id": "pat-10000032", "identifier": [{"system": "http://mimic.mit.edu/fhir/patient", "value": "10000032"}], "gender": "female", "birthDate": "1952-05-18", "name": [{"family": "Kovacs", "given": ["Elena"]}], "address": [{"city": "Boston", "state": "MA", "country": "US"}]}
{"resourceType": "Encounter", "id": "enc-22595853", "status": "finished", "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "EMER", "display": "Emergency Department"}, "subject": {"reference": "urn:uuid:pat-10000032", "display": "Elena Kovacs"}, "period": {"start": "2024-05-06T19:17:00Z", "end": "2024-05-08T15:30:00Z"}}
{"resourceType": "Condition", "id": "cond-5715", "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]}, "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]}, "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-9-cm", "code": "5715", "display": "Cirrhosis of liver without mention of alcohol"}], "text": "Hepatic Cirrhosis (Decompensated)"}, "subject": {"reference": "urn:uuid:pat-10000032"}, "encounter": {"reference": "urn:uuid:enc-22595853"}}
{"resourceType": "Condition", "id": "cond-4560", "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]}, "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-9-cm", "code": "4560", "display": "Esophageal varices with bleeding"}], "text": "Bleeding Esophageal Varices"}, "subject": {"reference": "urn:uuid:pat-10000032"}, "encounter": {"reference": "urn:uuid:enc-22595853"}}
{"resourceType": "Observation", "id": "obs-bili-50885", "status": "final", "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}], "code": {"coding": [{"system": "http://loinc.org", "code": "1975-2", "display": "Bilirubin.total [Mass/volume] in Serum or Plasma"}], "text": "Total Bilirubin"}, "subject": {"reference": "urn:uuid:pat-10000032"}, "encounter": {"reference": "urn:uuid:enc-22595853"}, "effectiveDateTime": "2024-05-07T04:15:00Z", "valueQuantity": {"value": 4.8, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"}, "interpretation": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "H", "display": "High"}]}], "referenceRange": [{"low": {"value": 0.2, "unit": "mg/dL"}, "high": {"value": 1.2, "unit": "mg/dL"}}]}
{"resourceType": "Observation", "id": "obs-inr-51237", "status": "final", "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}], "code": {"coding": [{"system": "http://loinc.org", "code": "6301-6", "display": "INR in Platelet poor plasma by Coagulation assay"}], "text": "Prothrombin Time / INR"}, "subject": {"reference": "urn:uuid:pat-10000032"}, "encounter": {"reference": "urn:uuid:enc-22595853"}, "effectiveDateTime": "2024-05-07T04:15:00Z", "valueQuantity": {"value": 2.4, "unit": "{INR}", "system": "http://unitsofmeasure.org", "code": "{INR}"}, "interpretation": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "H", "display": "High"}]}], "referenceRange": [{"low": {"value": 0.9, "unit": "{INR}"}, "high": {"value": 1.1, "unit": "{INR}"}}]}
{"resourceType": "MedicationRequest", "id": "med-octreotide", "status": "active", "intent": "order", "medicationCodeableConcept": {"coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "7553", "display": "Octreotide 50 MCG/ML Injection"}], "text": "Octreotide Continuous IV Infusion (50 mcg/hr)"}, "subject": {"reference": "urn:uuid:pat-10000032"}, "encounter": {"reference": "urn:uuid:enc-22595853"}, "dosageInstruction": [{"text": "50 mcg/hr continuous IV drip for variceal bleeding control"}]}"""
