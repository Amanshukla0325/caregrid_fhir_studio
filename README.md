# CareGrid FHIR Studio

Universal clinical document converter and FHIR R4 workbench. Converts legacy medical records, hospital messaging protocols, billing claims, and ICU cohorts into fully compliant HL7® FHIR® R4 Bundles with AST source mapping and interactive clinical graph visualization.

---

## Supported Formats

CareGrid FHIR Studio parses and transforms five primary healthcare document formats:

| Format | Source Specification | Supported Data Elements |
| :--- | :--- | :--- |
| **PDF Clinical Notes** | PyMuPDF text & block extraction | Patient demographics, admission status, primary/secondary diagnoses (ICD-10 / SNOMED), critical lab values (LOINC), therapeutic interventions (RxNorm) |
| **HL7v2 Feeds** | Dynamic delimiter negotiation (`\|^\~\\&`) | `MSH`, `PID`, `PV1`, `DG1`, `OBX` segments; unescapes delimiters and hex escape sequences (`\F\`, `\S\`, `\T\`, `\R\`, `\E\`, `\X0D0A\`) |
| **HL7v3 C-CDA XML** | Continuity of Care Document (CCD) | Allergies, Problems, Encounters, Vital Signs, Lab Results, Immunizations, Medications; handles CDA `nullFlavor` codes (`UNK`, `NASK`, `MSK`, `NA`) |
| **X12 837 EDI Claims** | Professional (837P) & Institutional (837I) | 3-level hierarchical loops (`2000A` Billing Provider, `2000B` Subscriber, `2000C` Patient), claim totals, diagnoses (`HI`), and service lines (`SV1`/`SV2`) |
| **MIMIC-IV / NDJSON** | PhysioNet FHIR Bulk Data (`.ndjson`, `.ndjson.gz`, `.gz`) | In-memory GZIP decompression (`0x1f 0x8b`), newline-delimited JSON streaming, ICU cohort aggregation |

---

## Core Capabilities

* **AST Source Map Engine (`utils/json_source_map.py`)**: Zero-dependency RFC 6901 JSON pointer parser and serializer. Computes exact character offsets, line numbers, and column bounding boxes (`key`, `keyEnd`, `value`, `valueEnd`) for every element in the FHIR output.
* **Force-Directed Clinical Graph (`utils/force_graph_renderer.py`)**: Bundled offline 2D force-directed canvas. Renders patient-centric care networks with 1-hop neighborhood highlighting and interactive node inspection.
* **Medplum-Grade Clinical View**: Patient demographics banner, encounter-grouped chronological timelines, and polymorphic value formatting (`valueQuantity`, `valueCodeableConcept`, reference ranges, abnormal flags).
* **Live FHIRPath Query Engine (`utils/fhirpath_evaluator.py`)**: Real-time expression evaluation directly against the converted FHIR bundle (e.g. `Patient.name.family`, `Observation.where(status = 'final')`).
* **Deterministic Resource Identity**: Deterministic UUIDv5 generation linked to canonical namespaces (`urn:uuid:...`).

---

## Quickstart

### Prerequisites
* Python 3.10+
* Git

### Installation

```bash
# Clone the repository
git clone https://github.com/Amanshukla0325/caregrid_fhir_studio.git
cd caregrid_fhir_studio

# Install dependencies
pip install -r requirements.txt
```

### Launch the Studio UI

```bash
streamlit run app.py
```
Open **`http://localhost:8501`** (or configured port) in your web browser.

### Run CLI Verification

Test the conversion pipeline and AST validation across all supported clinical formats:

```bash
# Verify all formats
python cli.py

# Test a specific format
python cli.py --sample pdf
python cli.py --sample hl7v2
python cli.py --sample cda
python cli.py --sample x12
python cli.py --sample mimic
```

---

## Project Structure

```
caregrid_fhir_studio/
├── .streamlit/
│   └── config.toml             # Monochrome design token configuration
├── converters/
│   ├── cda_converter.py        # HL7v3 C-CDA XML to FHIR R4
│   ├── hl7v2_converter.py      # HL7v2 pipe-delimited parser & converter
│   ├── ndjson_converter.py     # MIMIC-IV Bulk NDJSON & GZIP converter
│   ├── pdf_converter.py        # PyMuPDF clinical note extractor & parser
│   └── x12_converter.py        # X12 837 EDI claim to FHIR Claim / Bundle
├── samples/
│   └── marcus_vance_article2.pdf
├── utils/
│   ├── ast_validator.py        # Structural & reference integrity validator
│   ├── fhir_formatters.py      # Clinical summary & polymorphic formatters
│   ├── fhirpath_evaluator.py   # FHIRPath query engine
│   ├── force-graph.min.js      # Bundled offline graph library
│   ├── force_graph_renderer.py # 2D canvas visualization & inspector
│   ├── graph_crawler.py        # Reference graph crawler
│   ├── json_source_map.py      # Streaming AST source map parser
│   └── react-force-graph-2d.min.js
├── app.py                      # Streamlit application
├── cli.py                      # CLI test runner
├── requirements.txt
└── README.md
```

---

## Design Philosophy

The interface follows a strict black-and-white aesthetic (`#ffffff` / `#000000`, 1.5px/2px solid borders) built for high-density clinical review:
* Primary Typography: **Patrick Hand** for annotations and natural clinical text.
* Monospace Typography: **JetBrains Mono** for raw payloads, JSON paths, and code tokens.
* Zero external cloud telemetry; runs completely local and offline.

---

## License

MIT License.
