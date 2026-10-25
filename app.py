import streamlit as st
import streamlit.components.v1 as components
import json
import pandas as pd
from converters.hl7v2_converter import parse_hl7v2
from converters.cda_converter import parse_cda
from converters.x12_converter import parse_x12_837
from converters.pdf_converter import parse_pdf_note, extract_text_from_pdf
from converters.ndjson_converter import parse_ndjson, SAMPLE_MIMIC_IV
from utils.graph_crawler import build_fhir_graph
from utils.ast_validator import validate_fhir_bundle
from utils.fhir_formatters import build_clinical_summary
from utils.fhirpath_evaluator import eval_fhirpath
from utils.force_graph_renderer import render_force_graph_html

# Page Config
st.set_page_config(
    page_title="CareGrid FHIR Studio",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Minimalist Black & White + Patrick Hand Typography
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Patrick+Hand&family=JetBrains+Mono&display=swap');

/* Force Light Theme */
:root {
    --primary-color: #000000 !important;
    --background-color: #ffffff !important;
    --secondary-background-color: #ffffff !important;
    --text-color: #000000 !important;
    color-scheme: light !important;
}

html, body, .stApp, p, h1, h2, h3, h4, h5, h6, label, span, div {
    font-family: 'Patrick Hand', cursive, sans-serif !important;
}

body, .stApp {
    background-color: #ffffff !important;
    color: #000000 !important;
}

#MainMenu, header, footer {
    visibility: hidden;
    height: 0;
}

.block-container {
    padding-top: 1.8rem !important;
    padding-bottom: 2rem !important;
    max-width: 1050px !important;
}

.title-header {
    font-size: 2.2rem;
    font-weight: bold;
    border-bottom: 2px solid #000000;
    padding-bottom: 0.5rem;
    margin-bottom: 1.5rem;
    color: #000000;
}

/* File Uploader styling - Pure White Dropzone with Crisp 2px Black Border */
[data-testid="stFileUploader"] {
    background-color: #ffffff !important;
    border: none !important;
    padding: 0 !important;
}

[data-testid="stFileUploader"] label {
    font-size: 1.15rem !important;
    font-weight: bold !important;
    color: #000000 !important;
}

[data-testid="stFileUploaderDropzone"], [data-testid="stFileUploader"] section {
    background-color: #ffffff !important;
    border: 2px dashed #000000 !important;
    border-radius: 6px !important;
    padding: 24px 16px !important;
}

[data-testid="stFileUploaderDropzone"] * {
    color: #000000 !important;
    background-color: transparent !important;
}

/* Browse files button inside uploader (when empty) */
[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"],
[data-testid="stFileUploaderDropzone"] > div > span > button {
    background-color: #000000 !important;
    color: #ffffff !important;
    border: 1.5px solid #000000 !important;
    border-radius: 4px !important;
    font-family: 'Patrick Hand', cursive, sans-serif !important;
    font-size: 1.1rem !important;
    font-weight: bold !important;
    padding: 0.4rem 1.4rem !important;
    cursor: pointer !important;
}

[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"] *,
[data-testid="stFileUploaderDropzone"] > div > span > button * {
    color: #ffffff !important;
    fill: #ffffff !important;
    background-color: transparent !important;
}

[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stFileUploaderDropzone"] > div > span > button:hover {
    background-color: #333333 !important;
}

/* Uploaded File Chip Container */
[data-testid="stFileChips"] {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    justify-content: flex-start !important;
}

[data-testid="stFileChip"] {
    background-color: #ffffff !important;
    border: 1.5px solid #000000 !important;
    border-radius: 4px !important;
    padding: 6px 14px !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 12px !important;
    box-shadow: 2px 2px 0px #000000 !important;
}

[data-testid="stFileChipName"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.92rem !important;
    font-weight: bold !important;
    color: #000000 !important;
}

/* Clean Cross Button (x) to remove/delete the file */
[data-testid="stFileChipDeleteBtn"] {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin-left: 10px !important;
}

[data-testid="stFileChipDeleteBtn"] button {
    background-color: #ffffff !important;
    color: #000000 !important;
    border: 1.5px solid #000000 !important;
    border-radius: 50% !important;
    width: 24px !important;
    height: 24px !important;
    min-width: 24px !important;
    min-height: 24px !important;
    padding: 0 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}

[data-testid="stFileChipDeleteBtn"] button:hover {
    background-color: #000000 !important;
    color: #ffffff !important;
}

[data-testid="stFileChipDeleteBtn"] button svg {
    width: 14px !important;
    height: 14px !important;
    fill: currentColor !important;
    stroke: currentColor !important;
}

[data-testid="stFileChipDeleteBtn"] button:hover svg {
    fill: #ffffff !important;
    stroke: #ffffff !important;
}

/* Hide redundant "Add files" button in single-file mode */
[data-testid="stFileChips"] ~ button,
[data-testid="stFileChips"] + button,
[data-testid="stFileUploaderDropzone"] button[aria-label="Add files"] {
    display: none !important;
}

[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: #444444 !important;
    font-size: 1rem !important;
}

/* Clean Action Buttons - White Background, 1.5px Black Border, Black Text */
.stButton > button {
    background-color: #ffffff !important;
    color: #000000 !important;
    border: 1.5px solid #000000 !important;
    border-radius: 4px !important;
    font-family: 'Patrick Hand', cursive, sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: bold !important;
    padding: 0.4rem 1rem !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}

.stButton > button * {
    color: #000000 !important;
    background-color: transparent !important;
}

.stButton > button:hover {
    background-color: #000000 !important;
    color: #ffffff !important;
}

.stButton > button:hover * {
    color: #ffffff !important;
}

.stButton > button:disabled {
    opacity: 0.35 !important;
    cursor: not-allowed !important;
    border-color: #888888 !important;
    color: #888888 !important;
}

/* Download Button - Solid Black with White Text */
.stDownloadButton > button {
    background-color: #000000 !important;
    color: #ffffff !important;
    border: 1px solid #000000 !important;
    border-radius: 4px !important;
    font-family: 'Patrick Hand', cursive, sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: bold !important;
    padding: 0.4rem 1.2rem !important;
    cursor: pointer !important;
}

.stDownloadButton > button * {
    color: #ffffff !important;
    background-color: transparent !important;
}

.stDownloadButton > button:hover {
    background-color: #333333 !important;
}

/* Selectbox styling */
div[data-baseweb="select"] {
    border: 1.5px solid #000000 !important;
    border-radius: 4px !important;
    background-color: #ffffff !important;
}

div[data-baseweb="select"] * {
    font-family: 'Patrick Hand', cursive, sans-serif !important;
    color: #000000 !important;
    font-size: 1.05rem !important;
}

/* Radio buttons for representations */
.stRadio [data-testid="stWidgetLabel"] {
    display: none !important;
}

.stRadio label {
    font-size: 1.1rem !important;
    font-weight: bold !important;
    color: #000000 !important;
}

/* Text area & inputs */
textarea {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    border: 1.5px solid #000000 !important;
    border-radius: 4px !important;
    background-color: #ffffff !important;
    color: #000000 !important;
}

/* Code block */
pre, code, .stCodeBlock {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    background-color: #fafafa !important;
    color: #000000 !important;
    border: 1.5px solid #000000 !important;
    border-radius: 4px !important;
}

table {
    border-collapse: collapse !important;
    width: 100% !important;
    border: 1.5px solid #000000 !important;
    font-family: 'Patrick Hand', cursive !important;
}
th {
    background-color: #f0f0f0 !important;
    color: #000000 !important;
    border-bottom: 2px solid #000000 !important;
    padding: 8px !important;
    font-size: 1.05rem !important;
}
td {
    border-bottom: 1px solid #000000 !important;
    padding: 8px !important;
    font-size: 1rem !important;
    color: #000000 !important;
}

.placeholder-box {
    text-align: center;
    color: #222222;
    font-size: 1.25rem;
    border: 1.5px dashed #000000;
    padding: 2.5rem;
    border-radius: 6px;
    background-color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-header">CareGrid FHIR Studio</div>', unsafe_allow_html=True)

# Predefined Sample Texts
SAMPLE_PDF = """CAREGRID CLINICAL DISCHARGE & LAB REPORT
PATIENT: Marcus D. Vance | MRN: MRN-994821 | DOB: 06/14/1982 | Gender: Male
ADMISSION: March 10, 2024 | Status: Inpatient Encounter (IMP)

PRIMARY DIAGNOSIS:
1. Disseminated Histoplasmosis (ICD-10: B39.4, SNOMED: 20562009) - Active, Confirmed

LABORATORY INVESTIGATIONS:
1. CD4+ T-Lymphocyte Count (LOINC: 24467-3): 118 cells/uL [CRITICAL LOW, LL] (Ref: 500-1500 cells/uL)
2. Histoplasma capsulatum Antigen, Urine (LOINC: 43407-6): POSITIVE (4.8 EIA units)

THERAPEUTIC INTERVENTIONS:
1. Liposomal Amphotericin B (RxNorm: 142133): 3 mg/kg IV once daily induction therapy"""

SAMPLE_HL7V2 = """MSH|^~\\&|EPIC|HOSPITAL|CAREGRID|STUDIO|20240218101500||ADT^A01^ADT_A01|MSG-99281|P|2.5.1
PID|1||MRN-334182^^^Hospital^MR||Kim^David^J||19680928|M
PV1|1|I|WARD1^ROOM102^BED1||||1144229988^Chen^Stephanie^L^^^Dr.
DG1|1|I10|E11.65^Type 2 diabetes mellitus with hyperglycemia^ICD10CM|Type 2 Diabetes Mellitus|20240218101500|A
OBX|1|NM|2345-7^Glucose [Mass/volume] in Serum or Plasma^LN|1|248|mg/dL|70-99|H|||F
OBX|2|NM|4548-4^Hemoglobin A1c/Hemoglobin.total in Blood^LN|1|9.4|%|<5.7|H|||F"""

SAMPLE_CDA = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <id root="2.16.840.1.113883.19.5.99999.1" extension="CCD-2024-001"/>
  <title>CareGrid Continuity of Care Document</title>
  <recordTarget>
    <patientRole>
      <id root="2.16.840.1.113883.4.1" extension="SSN-223344"/>
      <patient>
        <name><given>Sarah</given><family>Jenkins</family></name>
        <administrativeGenderCode code="F"/>
      </patient>
    </patientRole>
  </recordTarget>
  <component>
    <structuredBody>
      <component>
        <section>
          <code code="46240-8" displayName="Encounters"/>
          <entry>
            <encounter classCode="ENC">
              <id extension="enc-ccda-ambulatory-visit"/>
              <code code="AMB" displayName="Ambulatory"/>
            </encounter>
          </entry>
        </section>
      </component>
      <component>
        <section>
          <code code="11450-4" displayName="Problem List"/>
          <entry>
            <observation classCode="OBS">
              <code code="N18.30" displayName="Chronic kidney disease, stage 3 unspecified"/>
            </observation>
          </entry>
        </section>
      </component>
      <component>
        <section>
          <code code="30954-2" displayName="Laboratory Results"/>
          <entry>
            <observation classCode="OBS">
              <code code="2160-0" displayName="Creatinine [Mass/volume] in Serum"/>
              <value value="1.72" unit="mg/dL"/>
            </observation>
          </entry>
        </section>
      </component>
    </structuredBody>
  </component>
</ClinicalDocument>"""

SAMPLE_X12 = """ISA*00*          *00*          *ZZ*SUBMITTER01    *ZZ*PAYER00912     *240312*1422*^*00501*000000001*0*P*:~
GS*HC*SUBMITTER01*PAYER00912*20240312*1422*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*CLM883719*20240312*1422*CH~
NM1*41*2*CAREGRID SUBMITTER*****46*SUBMITTER01~
NM1*40*2*BLUESHIELD ILLINOIS PPO*****46*PAYER00912~
NM1*85*1*STERLING*ARTHUR*B***XX*1982736450~
NM1*IL*1*REYNOLDS*ELEANOR*ROSE***MI*MEM-883719~
CLM*CLM883719*250.00***11:B:1*Y*A*Y*Y~
HI*BK:I10~
LX*1~
SV1*HC:99214*185.00*UN*1***1~
DTP*472*D8*20240311~
LX*2~
SV1*HC:93000*65.00*UN*1***1~
DTP*472*D8*20240311~
SE*15*0001~
GE*1*1~
IEA*1*000000001~"""

# Manage Session State
if "doc_content" not in st.session_state:
    st.session_state.doc_content = None
if "doc_format" not in st.session_state:
    st.session_state.doc_format = None
if "doc_name" not in st.session_state:
    st.session_state.doc_name = None
if "doc_source" not in st.session_state:
    st.session_state.doc_source = None
if "resource_pos" not in st.session_state:
    st.session_state.resource_pos = 0

# 1. Document Uploading Button
uploaded_file = st.file_uploader(
    "Upload Clinical Document (PDF, HL7v2, C-CDA XML, X12 837, MIMIC-IV NDJSON, .GZ)",
    type=["txt", "edi", "x12", "hl7", "xml", "json", "pdf", "ndjson", "gz"]
)

# When user clicks the cross button (x) on the file uploader to remove/delete the file,
# reset the studio session state so the document actually goes away.
if uploaded_file is None and st.session_state.get("doc_source") == "upload":
    st.session_state.doc_content = None
    st.session_state.doc_format = None
    st.session_state.doc_name = None
    st.session_state.doc_source = None
    st.session_state.resource_pos = 0

# Sample Quick-Load Buttons
st.markdown("<div style='font-size: 1.15rem; font-weight: bold; margin-top: 14px; margin-bottom: 8px;'>Or load a verified sample:</div>", unsafe_allow_html=True)
b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)

with b_col1:
    if st.button("PDF Note", use_container_width=True):
        st.session_state.doc_content = SAMPLE_PDF
        st.session_state.doc_format = "pdf"
        st.session_state.doc_name = "Marcus_Vance_Discharge_Note.pdf"
        st.session_state.doc_source = "sample"
        st.session_state.resource_pos = 0

with b_col2:
    if st.button("HL7v2", use_container_width=True):
        st.session_state.doc_content = SAMPLE_HL7V2
        st.session_state.doc_format = "hl7v2"
        st.session_state.doc_name = "ADT_A01_David_Kim.hl7"
        st.session_state.doc_source = "sample"
        st.session_state.resource_pos = 0

with b_col3:
    if st.button("HL7v3 CDA", use_container_width=True):
        st.session_state.doc_content = SAMPLE_CDA
        st.session_state.doc_format = "cda"
        st.session_state.doc_name = "Sarah_Jenkins_CCD.xml"
        st.session_state.doc_source = "sample"
        st.session_state.resource_pos = 0

with b_col4:
    if st.button("X12 837 Claim", use_container_width=True):
        st.session_state.doc_content = SAMPLE_X12
        st.session_state.doc_format = "x12"
        st.session_state.doc_name = "Professional_Claim_837P.edi"
        st.session_state.doc_source = "sample"
        st.session_state.resource_pos = 0

with b_col5:
    if st.button("MIMIC-IV (ICU)", use_container_width=True):
        st.session_state.doc_content = SAMPLE_MIMIC_IV
        st.session_state.doc_format = "ndjson"
        st.session_state.doc_name = "MimicCohort_Elena_Kovacs.ndjson"
        st.session_state.doc_source = "sample"
        st.session_state.resource_pos = 0

if uploaded_file is not None:
    raw_bytes = uploaded_file.read()
    file_name = uploaded_file.name.lower()
    st.session_state.doc_name = uploaded_file.name
    st.session_state.doc_source = "upload"
    st.session_state.resource_pos = 0

    # Auto-decompress if GZIP (.gz extension or magic bytes 0x1f, 0x8b)
    if file_name.endswith(".gz") or (len(raw_bytes) >= 2 and raw_bytes[:2] == b'\x1f\x8b'):
        try:
            import gzip
            raw_bytes = gzip.decompress(raw_bytes)
            if file_name.endswith(".gz"):
                file_name = file_name[:-3]
        except Exception as gz_err:
            st.error(f"Failed to decompress GZIP archive: {gz_err}")

    if file_name.endswith(".pdf") or raw_bytes.startswith(b"%PDF"):
        st.session_state.doc_format = "pdf"
        st.session_state.doc_content = extract_text_from_pdf(raw_bytes)
    else:
        content = raw_bytes.decode("utf-8", errors="ignore")
        st.session_state.doc_content = content
        if "MSH|^~" in content:
            st.session_state.doc_format = "hl7v2"
        elif "ISA*" in content:
            st.session_state.doc_format = "x12"
        elif "<ClinicalDocument" in content:
            st.session_state.doc_format = "cda"
        elif file_name.endswith(".ndjson") or ("\n{" in content and '"resourceType"' in content):
            st.session_state.doc_format = "ndjson"
        elif content.strip().startswith("{") and '"resourceType"' in content:
            st.session_state.doc_format = "ndjson"
        else:
            st.session_state.doc_format = "pdf"

# 2. Visual Representation (Only displayed AFTER uploading or sample selection)
if st.session_state.doc_content:
    content = st.session_state.doc_content
    fmt = st.session_state.doc_format

    # Run Conversion Engine
    if fmt == "hl7v2":
        bundle = parse_hl7v2(content)
    elif fmt == "cda":
        bundle = parse_cda(content)
    elif fmt == "x12":
        bundle = parse_x12_837(content)
    elif fmt == "ndjson":
        bundle = parse_ndjson(content)
    else:
        bundle = parse_pdf_note(content)

    bundle_json = json.dumps(bundle, indent=2)
    entries = bundle.get("entry", [])

    st.markdown("<hr style='border: 1px solid #000000; margin-top: 18px; margin-bottom: 18px;'>", unsafe_allow_html=True)
    
    # Header bar after upload
    head_col1, head_col2, head_col3, head_col4 = st.columns([1.5, 2.1, 0.9, 0.5])
    with head_col1:
        st.markdown(f"<span style='font-size: 1.35rem; font-weight: bold;'>{st.session_state.doc_name}</span> &nbsp;|&nbsp; <b>{len(entries)} FHIR R4 Resources</b>", unsafe_allow_html=True)
    with head_col2:
        view_mode = st.radio("View:", ["Clinical View", "Code (JSON)", "Validation & References", "Graph"], horizontal=True)
    with head_col3:
        st.download_button(
            label="Download FHIR JSON",
            data=bundle_json,
            file_name=f"fhir_{fmt}.json",
            mime="application/json",
            use_container_width=True
        )
    with head_col4:
        if st.button("✕ Clear", use_container_width=True, help="Close document and clear workbench"):
            st.session_state.doc_content = None
            st.session_state.doc_format = None
            st.session_state.doc_name = None
            st.session_state.doc_source = None
            st.session_state.resource_pos = 0
            st.rerun()

    # Representation 0: Clinical View (Medplum Demographics Banner & Encounter Timeline)
    if view_mode == "Clinical View":
        clin_summary = build_clinical_summary(bundle)
        patient = clin_summary["patient"]
        encounters = clin_summary["encounters"]
        other_records = clin_summary["other_records"]
        total_items = sum(len(e["items"]) for e in encounters) + len(other_records)

        # Patient Demographics Banner (Medplum Style)
        st.markdown(f"""
        <div style="border: 2px solid #000000; border-radius: 4px; padding: 16px 20px; background-color: #ffffff; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid #000000; padding-bottom: 8px; margin-bottom: 12px;">
                <div>
                    <span style="font-size: 1.6rem; font-weight: bold;">{patient['name']}</span>
                </div>
                <div style="font-size: 1.05rem; font-family: 'JetBrains Mono', monospace;">
                    MRN: <b>{patient['mrn']}</b>
                </div>
            </div>
            <div style="display: flex; gap: 32px; font-size: 1.1rem; color: #222222; flex-wrap: wrap;">
                <div>Gender: <b>{patient['gender']}</b></div>
                <div>DOB: <b>{patient['dob']}</b></div>
                <div>Encounters: <b>{len(encounters)}</b></div>
                <div>Clinical Events: <b>{total_items}</b></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Encounter Timeline
        if encounters:
            st.markdown("<div style='font-size: 1.3rem; font-weight: bold; margin-bottom: 12px;'>Encounter Timeline</div>", unsafe_allow_html=True)
            for enc in encounters:
                st.markdown(f"""
                <div style="border: 1.5px solid #000000; border-radius: 4px; padding: 14px 18px; margin-bottom: 16px; background-color: #fafafa;">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #000000; padding-bottom: 6px; margin-bottom: 12px;">
                        <div style="font-size: 1.25rem; font-weight: bold;">{enc['title']}</div>
                        <div style="font-size: 1.05rem; font-family: 'JetBrains Mono', monospace;">Date: {enc['period']} | Status: {enc['status']}</div>
                    </div>
                """, unsafe_allow_html=True)

                if enc["items"]:
                    for item in enc["items"]:
                        date_badge = f"<span style='font-size: 0.95rem; color: #444444; font-family: \"JetBrains Mono\", monospace;'>Date: {item['date']}</span>" if item['date'] != "—" else ""
                        st.markdown(f"""
                        <div style="border: 1px solid #000000; border-radius: 3px; background-color: #ffffff; padding: 10px 14px; margin-bottom: 10px;">
                            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                                <span style="font-size: 1.15rem; font-weight: bold;">{item['title']}</span>
                                <span style="font-size: 0.9rem; font-family: 'JetBrains Mono', monospace; border: 1px solid #000000; padding: 1px 6px; border-radius: 2px;">{item['resourceType']}</span>
                            </div>
                            <div style="font-size: 1.05rem; margin-top: 4px; color: #111111;">{item['detail']}</div>
                            {f"<div style='margin-top: 4px;'>{date_badge}</div>" if date_badge else ""}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("<div style='font-size: 1.05rem; color: #666666;'>No nested clinical records under this encounter.</div>", unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

        # Other / Unattached Clinical Records
        if other_records:
            st.markdown(f"<div style='font-size: 1.3rem; font-weight: bold; margin-top: 20px; margin-bottom: 12px;'>Longitudinal & Unattached Records ({len(other_records)})</div>", unsafe_allow_html=True)
            for item in other_records:
                date_badge = f"<span style='font-size: 0.95rem; color: #444444; font-family: \"JetBrains Mono\", monospace;'>Date: {item['date']}</span>" if item['date'] != "—" else ""
                st.markdown(f"""
                <div style="border: 1.5px solid #000000; border-radius: 4px; background-color: #ffffff; padding: 12px 16px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: baseline;">
                        <span style="font-size: 1.2rem; font-weight: bold;">{item['title']}</span>
                        <span style="font-size: 0.9rem; font-family: 'JetBrains Mono', monospace; border: 1px solid #000000; padding: 1px 6px; border-radius: 2px;">{item['resourceType']}</span>
                    </div>
                    <div style="font-size: 1.05rem; margin-top: 4px; color: #111111;">{item['detail']}</div>
                    {f"<div style='margin-top: 4px;'>{date_badge}</div>" if date_badge else ""}
                </div>
                """, unsafe_allow_html=True)

    # Representation 1: Code (JSON)
    elif view_mode == "Code (JSON)":
        val_result = validate_fhir_bundle(bundle, bundle_json)
        dependencies = val_result.get("dependencies", [])

        c_view_opt1, c_view_opt2 = st.columns([2, 1])
        with c_view_opt1:
            code_view_style = st.radio(
                "Display Mode:",
                ["Full Bundle JSON", "Step-Through Inspector"],
                horizontal=True,
                label_visibility="collapsed"
            )

        if code_view_style == "Full Bundle JSON":
            c_left, c_right = st.columns(2)
            with c_left:
                st.markdown("<div style='font-size: 1.15rem; font-weight: bold;'>Source Document</div>", unsafe_allow_html=True)
                st.text_area("Source Text", value=content, height=480, label_visibility="collapsed")
            with c_right:
                st.markdown(f"<div style='font-size: 1.15rem; font-weight: bold;'>Converted FHIR R4 Bundle ({len(entries)} resources)</div>", unsafe_allow_html=True)
                st.code(bundle_json, language="json")
        else:
            # Single-Resource Step-Through (FRED BundleBar & RefWarning)
            if not entries:
                st.warning("Bundle contains no resources.")
            else:
                n_res = len(entries)
                curr_idx = min(max(st.session_state.get("resource_pos", 0), 0), n_res - 1)
                
                # Bundle-Bar controls
                st.markdown("<div style='margin-top: 4px; margin-bottom: 8px;'>", unsafe_allow_html=True)
                bar_c1, bar_c2, bar_c3, bar_c4, bar_c5 = st.columns([0.8, 0.8, 3.4, 0.8, 0.8])
                
                with bar_c1:
                    if st.button("<< First", disabled=(curr_idx == 0), key="btn_first", use_container_width=True):
                        st.session_state.resource_pos = 0
                        st.rerun()
                with bar_c2:
                    if st.button("< Prev", disabled=(curr_idx == 0), key="btn_prev", use_container_width=True):
                        st.session_state.resource_pos = max(0, curr_idx - 1)
                        st.rerun()
                with bar_c3:
                    resource_labels = [
                        f"Resource {i+1} of {n_res}: {e.get('resource', {}).get('resourceType')} (#{e.get('resource', {}).get('id', '')[:8]})"
                        for i, e in enumerate(entries)
                    ]
                    selected_label = st.selectbox(
                        "Jump to Resource",
                        options=resource_labels,
                        index=curr_idx,
                        label_visibility="collapsed",
                        key="sb_res_nav"
                    )
                    selected_idx = resource_labels.index(selected_label)
                    if selected_idx != curr_idx:
                        st.session_state.resource_pos = selected_idx
                        st.rerun()
                with bar_c4:
                    if st.button("Next >", disabled=(curr_idx >= n_res - 1), key="btn_next", use_container_width=True):
                        st.session_state.resource_pos = min(n_res - 1, curr_idx + 1)
                        st.rerun()
                with bar_c5:
                    if st.button("Last >>", disabled=(curr_idx >= n_res - 1), key="btn_last", use_container_width=True):
                        st.session_state.resource_pos = n_res - 1
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                # Selected Resource Context & FRED Ref Warning Banner
                curr_entry = entries[curr_idx]
                curr_res = curr_entry.get("resource", {})
                curr_type = curr_res.get("resourceType", "Resource")
                curr_id = curr_res.get("id", "")
                curr_dep = dependencies[curr_idx] if curr_idx < len(dependencies) else {}
                
                in_count = curr_dep.get("Inbound Degree", 0)
                out_count = curr_dep.get("Outbound Degree", 0)
                role = curr_dep.get("Topology Role", "Direct Leaf")
                ref_by = curr_dep.get("Referenced By", "None (0)")
                ref_out = curr_dep.get("References Out", "None (0)")

                # FRED-style Reference Warning / Hub Banner
                if in_count > 0:
                    banner_html = f"""
                    <div style="border: 2px solid #000000; padding: 10px 16px; margin-bottom: 12px; background: #fafafa; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <b>Inbound Link Notice:</b> This resource is referenced by <b>{in_count}</b> other resource(s) in this bundle.<br>
                            <span style="font-size: 0.95rem; color: #333333;">Sources: {ref_by}</span>
                        </div>
                        <div style="border: 1px solid #000000; padding: 2px 8px; border-radius: 3px; font-weight: bold; background: #ffffff;">
                            {role}
                        </div>
                    </div>
                    """
                else:
                    banner_html = f"""
                    <div style="border: 1.5px solid #000000; padding: 10px 16px; margin-bottom: 12px; background: #ffffff; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <b>Direct Edge (Leaf):</b> 0 inbound references. Points to {out_count} target(s).<br>
                            <span style="font-size: 0.95rem; color: #333333;">Targets: {ref_out}</span>
                        </div>
                        <div style="border: 1px solid #000000; padding: 2px 8px; border-radius: 3px; font-weight: bold; background: #fafafa;">
                            {role}
                        </div>
                    </div>
                    """
                st.markdown(banner_html, unsafe_allow_html=True)

                col_res_l, col_res_r = st.columns([1, 1])
                with col_res_l:
                    st.markdown("<div style='font-size: 1.15rem; font-weight: bold;'>Source Context</div>", unsafe_allow_html=True)
                    st.text_area("Source Text", value=content, height=440, label_visibility="collapsed", key="txt_single_src")
                with col_res_r:
                    r_head1, r_head2 = st.columns([2, 1])
                    with r_head1:
                        st.markdown(f"<div style='font-size: 1.15rem; font-weight: bold;'>{curr_type} (#{curr_id[:8]})</div>", unsafe_allow_html=True)
                    with r_head2:
                        st.download_button(
                            label="Download Resource",
                            data=json.dumps(curr_res, indent=2),
                            file_name=f"{curr_type}_{curr_id[:8]}.json",
                            mime="application/json",
                            use_container_width=True,
                            key="btn_dl_single"
                        )
                    st.code(json.dumps(curr_res, indent=2), language="json")

        # Medplum-Style Live FHIRPath Query Bar
        st.markdown("<hr style='border: 1px solid #000000; margin-top: 24px; margin-bottom: 16px;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 1.25rem; font-weight: bold; margin-bottom: 4px;'>Live FHIRPath Query Bar</div>", unsafe_allow_html=True)
        st.markdown("<div style='color: #444444; font-size: 1.05rem; margin-bottom: 10px;'>Evaluate standard FHIRPath expressions against this converted FHIR R4 bundle:</div>", unsafe_allow_html=True)

        if "fhirpath_expr" not in st.session_state:
            st.session_state.fhirpath_expr = "Patient.name.family"

        preset_cols = st.columns([1, 1, 1, 1.2, 1])
        with preset_cols[0]:
            if st.button("Patient Family", key="fp_btn_pat", use_container_width=True):
                st.session_state.fhirpath_expr = "Patient.name.family"
                st.rerun()
        with preset_cols[1]:
            if st.button("All Diagnoses", key="fp_btn_diag", use_container_width=True):
                st.session_state.fhirpath_expr = "Condition.code.text"
                st.rerun()
        with preset_cols[2]:
            if st.button("Lab Values", key="fp_btn_obs", use_container_width=True):
                st.session_state.fhirpath_expr = "Observation.valueQuantity.value"
                st.rerun()
        with preset_cols[3]:
            if st.button("Critical CD4 Lab", key="fp_btn_cd4", use_container_width=True):
                st.session_state.fhirpath_expr = "Observation.where(code.coding.code = '24467-3').valueQuantity.value"
                st.rerun()
        with preset_cols[4]:
            if st.button("Total Claim", key="fp_btn_clm", use_container_width=True):
                st.session_state.fhirpath_expr = "Claim.total.value"
                st.rerun()

        fp_input = st.text_input(
            "Expression",
            value=st.session_state.fhirpath_expr,
            key="fp_input_field",
            placeholder="e.g. Patient.name.family or Observation.where(code.coding.code = '24467-3').valueQuantity.value",
            label_visibility="collapsed"
        )
        if fp_input != st.session_state.fhirpath_expr:
            st.session_state.fhirpath_expr = fp_input

        fp_results = eval_fhirpath(fp_input, bundle)
        n_match = len(fp_results)

        st.markdown(f"<div style='font-size: 1.1rem; font-weight: bold; margin-top: 10px; margin-bottom: 6px;'>Evaluated Results ({n_match} matches):</div>", unsafe_allow_html=True)
        if fp_results:
            st.code(json.dumps(fp_results, indent=2), language="json")
        else:
            st.markdown("<div style='border: 1.5px dashed #000000; padding: 12px; border-radius: 4px; font-size: 1.05rem; color: #555555; background-color: #ffffff;'>No matching elements found for this FHIRPath expression in the current bundle.</div>", unsafe_allow_html=True)

    # Representation 2: Validation & References
    elif view_mode == "Validation & References":
        val_result = validate_fhir_bundle(bundle, bundle_json)
        
        # Conformance Scorecard Header
        score = val_result["conformance_score"]
        p_chk = val_result["passed_checks"]
        t_chk = val_result["total_checks"]
        st.markdown(f"""
        <div style="border: 2px solid #000000; padding: 12px 18px; margin-bottom: 18px; background: #ffffff; display: flex; justify-content: space-between; align-items: center; border-radius: 4px;">
            <div>
                <span style="font-size: 1.4rem; font-weight: bold;">FHIR R4 Conformance: {score}%</span>
                <span style="font-size: 1.1rem; margin-left: 14px;">({p_chk} of {t_chk} rules passed across 5 clinical dimensions)</span>
            </div>
            <div style="font-size: 1.15rem; font-weight: bold;">Conformance Scorecard</div>
        </div>
        """, unsafe_allow_html=True)

        # Section A: Resource Centrality & Dependency Degrees (FRED Hub Analysis)
        st.markdown("<div style='font-size: 1.2rem; font-weight: bold; margin-bottom: 6px;'>Resource Centrality & Dependency Degrees</div>", unsafe_allow_html=True)
        st.markdown("<div style='color: #444444; font-size: 1.05rem; margin-bottom: 8px;'>Inbound reference counting and topological network role for each resource:</div>", unsafe_allow_html=True)
        dep_df = pd.DataFrame([{
            "Resource": d["Resource"],
            "Topology Role": d["Topology Role"],
            "Inbound Degree": d["Inbound Degree"],
            "Outbound Degree": d["Outbound Degree"],
            "Referenced By (Inbound Sources)": d["Referenced By"],
            "References Out (Outbound Targets)": d["References Out"]
        } for d in val_result["dependencies"]])
        st.dataframe(dep_df, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Section B: Reference Links & Previews (SMART-on-FHIR language extension)
        st.markdown("<div style='font-size: 1.2rem; font-weight: bold; margin-bottom: 6px;'>Clinical References & Target Links</div>", unsafe_allow_html=True)
        st.markdown("<div style='color: #444444; font-size: 1.05rem; margin-bottom: 8px;'>Internal references with exact line coordinates and target previews:</div>", unsafe_allow_html=True)
        if val_result["references"]:
            ref_df = pd.DataFrame(val_result["references"])
            st.dataframe(ref_df[["Line", "Column", "Source Resource", "Target Reference", "Target Type", "Target Preview"]], use_container_width=True)
        else:
            st.info("No internal references in this bundle.")

        st.markdown("<br>", unsafe_allow_html=True)

        # Section C: Conformance Checks Breakdown (including FRED primitive regexes)
        st.markdown("<div style='font-size: 1.2rem; font-weight: bold; margin-bottom: 6px;'>Conformance Rule Checks & AST Coordinates</div>", unsafe_allow_html=True)
        checks_df = pd.DataFrame(val_result["checks"])
        st.dataframe(checks_df[["Dimension", "Rule Tested", "Status", "JSON Pointer", "Line", "Column", "Details"]], use_container_width=True)

    # Representation 3: Graph View (ForceGraph2D Interactive Clinical Network)
    else:
        st.markdown("<div style='font-size: 1.25rem; font-weight: bold; margin-bottom: 4px;'>Care Network ForceGraph2D</div>", unsafe_allow_html=True)
        st.markdown("<div style='color: #444444; font-size: 1.05rem; margin-bottom: 12px;'>Pure monochrome clinical cluster. Click any node to inspect its exact fields and connected references without losing care network context:</div>", unsafe_allow_html=True)

        force_html = render_force_graph_html(bundle, height=620)
        components.html(force_html, height=640)

        graph_data = build_fhir_graph(bundle)
        nodes = graph_data["nodes"]
        links = graph_data["links"]

        st.markdown("<br>", unsafe_allow_html=True)
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown(f"<div style='font-size: 1.15rem; font-weight: bold;'>Resolved Nodes ({len(nodes)})</div>", unsafe_allow_html=True)
            node_table = [{"ID": n["id"][:8], "Type": n["resourceType"], "Label": n["label"], "Weight": n.get("val", 10)} for n in nodes]
            st.dataframe(pd.DataFrame(node_table), use_container_width=True)
        with col_g2:
            st.markdown(f"<div style='font-size: 1.15rem; font-weight: bold;'>Recursive Reference Pointers ({len(links)})</div>", unsafe_allow_html=True)
            link_table = [{"Source": l["source"][:8] if isinstance(l["source"], str) else str(l["source"]), "Target": l["target"][:8] if isinstance(l["target"], str) else str(l["target"]), "Relation": l["relation"]} for l in links]
            st.dataframe(pd.DataFrame(link_table), use_container_width=True)
else:
    st.markdown("<br><div class='placeholder-box'>Upload a document above or click a verified sample to view the converted FHIR representation.</div>", unsafe_allow_html=True)
