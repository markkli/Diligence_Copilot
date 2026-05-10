from pathlib import Path
import json
import re

import streamlit as st

from diligence_engine import generate_company_outputs, slugify_company_name


st.set_page_config(
    page_title="Diligence Workspace",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

PACKAGE_PATTERN = "*_diligence_package.json"
DATA_DIR = Path("Data")
PRIMARY_ORDER = [
    "Commercial Diligence Memo",
    "Risk Dashboard",
    "Company Overview",
    "Investment Committee Summary",
    "Evidence Table",
    "Diligence Questions",
    "Source Documents",
]
SECTION_LABELS = {
    "company_overview": "Company Overview",
    "commercial_diligence_memo": "Commercial Diligence Memo",
    "investment_committee_summary": "Investment Committee Summary",
    "risk_dashboard": "Risk Dashboard",
    "evidence_table": "Evidence Table",
    "diligence_questions": "Diligence Questions",
    "source_documents": "Source Documents",
}


def find_package_files():
    return sorted(Path(".").glob(PACKAGE_PATTERN))


def prettify_company_name_from_slug(slug: str) -> str:
    return slug.replace("_", " ").title()


def package_slug_to_name(package_path: Path) -> str:
    slug = package_path.stem.replace("_diligence_package", "")
    return prettify_company_name_from_slug(slug)


def load_package(package_path: Path):
    return json.loads(package_path.read_text())


def package_to_sections(package: dict):
    sections = {}
    for key, label in SECTION_LABELS.items():
        value = package.get(key)
        if value is None:
            continue
        sections[label] = value
    return sections


def convert_bracket_subheaders(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            lines.append(f"### {stripped[1:-1]}")
        else:
            lines.append(line)
    return "\n".join(lines)


def convert_risk_register(text: str) -> str:
    converted = re.sub(r"(?m)^(\d+)\)\s*Risk Name:\s*(.+)$", r"#### Risk \1\n- **Risk Name:** \2", text)
    converted = re.sub(r"(?m)^- Category:\s*(.+)$", r"- **Category:** \1", converted)
    converted = re.sub(r"(?m)^- Description:\s*(.+)$", r"- **Description:** \1", converted)
    converted = re.sub(r"(?m)^- Evidence:\s*(.+)$", r"- **Evidence:** \1", converted)
    converted = re.sub(r"(?m)^- Severity:\s*(.+)$", r"- **Severity:** \1", converted)
    converted = re.sub(r"(?m)^- Confidence:\s*(.+)$", r"- **Confidence:** \1", converted)
    return converted


def convert_management_questions(text: str) -> str:
    lines = []
    q_num = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("Question:"):
            q_num += 1
            question = line.replace("Question:", "", 1).strip()
            lines.append(f"#### Question {q_num}")
            lines.append(f"- **Question:** {question}")
        elif line.startswith("Why it matters:"):
            why = line.replace("Why it matters:", "", 1).strip()
            lines.append(f"- **Why it matters:** {why}")
        elif line.startswith("Evidence prompting the question:"):
            ev = line.replace("Evidence prompting the question:", "", 1).strip()
            lines.append(f"- **Evidence prompting the question:** {ev}")
        else:
            lines.append(raw_line)
    return "\n".join(lines)


def format_generic_section(text: str) -> str:
    return convert_bracket_subheaders(text)


def render_source_documents(section_value):
    st.subheader("Source Documents")

    if not isinstance(section_value, list) or len(section_value) == 0:
        st.markdown("Not generated yet")
        return

    cols = st.columns(2)
    for idx, item in enumerate(section_value):
        document = item.get("document", "Unknown document")
        pages = item.get("pages", [])
        page_text = ", ".join(str(page) for page in pages) if pages else "Pages not available"

        with cols[idx % 2]:
            st.markdown(f"**{document}**")
            st.caption(f"Pages: {page_text}")


def get_section_display_text(section_value):
    if section_value is None:
        return "Not generated yet"
    if isinstance(section_value, dict) and "output" in section_value:
        return section_value["output"]
    return str(section_value)


def render_section(title: str, section_value):
    if title == "Source Documents":
        render_source_documents(section_value)
        return

    content = get_section_display_text(section_value)
    st.subheader(title)

    if title == "Risk Dashboard":
        st.markdown(convert_risk_register(content))
        return

    if title == "Diligence Questions":
        st.markdown(convert_management_questions(content))
        return

    st.markdown(format_generic_section(content))


def ordered_sections(section_dict: dict):
    seen = set()
    ordered = []
    for name in PRIMARY_ORDER:
        if name in section_dict:
            ordered.append((name, section_dict[name]))
            seen.add(name)
    for name, content in section_dict.items():
        if name not in seen:
            ordered.append((name, content))
    return ordered


def count_source_docs(section_value):
    if isinstance(section_value, list):
        return len(section_value)
    return 0


def existing_company_names():
    names = set()
    if DATA_DIR.exists():
        for path in DATA_DIR.iterdir():
            if path.is_dir():
                names.add(path.name)
    for package_file in find_package_files():
        names.add(package_slug_to_name(package_file))
    return sorted(names)


def package_path_for_company(company_name: str) -> Path:
    return Path(f"{slugify_company_name(company_name)}_diligence_package.json")


def save_uploaded_files(company_name: str, uploaded_files) -> Path:
    company_folder = DATA_DIR / company_name
    company_folder.mkdir(parents=True, exist_ok=True)
    for uploaded_file in uploaded_files:
        (company_folder / uploaded_file.name).write_bytes(uploaded_file.getbuffer())
    return company_folder


st.title("Diligence Workspace")
st.caption(
    "A first-pass commercial due diligence workspace that can now ingest PDFs, generate a diligence package, and render the structured output."
)

DATA_DIR.mkdir(exist_ok=True)
companies = existing_company_names()
default_company = companies[0] if companies else "Guidewire"
selected_existing_company = st.sidebar.selectbox("Company", companies if companies else [default_company])
new_company_name = st.sidebar.text_input("Or create new company", value="")
selected_company = new_company_name.strip() or selected_existing_company

st.sidebar.header("Workspace")
st.sidebar.markdown(f"**Company:** {selected_company}")
company_folder = DATA_DIR / selected_company
company_folder.mkdir(parents=True, exist_ok=True)

existing_docs = sorted(path.name for path in company_folder.glob("*.pdf"))
st.sidebar.markdown(f"**Current documents:** {len(existing_docs)}")
if existing_docs:
    with st.sidebar.expander("View company files"):
        for doc in existing_docs:
            st.markdown(f"- {doc}")

st.sidebar.header("Uploads")
uploaded_files = st.sidebar.file_uploader(
    "Upload company PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.sidebar.caption(f"{len(uploaded_files)} file(s) ready to save")
    if st.sidebar.button("Save uploaded files", use_container_width=True):
        save_uploaded_files(selected_company, uploaded_files)
        st.sidebar.success("Files saved to company folder.")
        st.rerun()

st.sidebar.header("Generation")
if st.sidebar.button("Generate Diligence Package", use_container_width=True):
    with st.spinner("Generating chunks, embeddings, package, and report. This may take a while..."):
        package, chunks_path, package_path, report_path = generate_company_outputs(
            company_name=selected_company,
            company_folder=company_folder,
            base_dir=Path("."),
        )
    st.session_state["last_generated_company"] = selected_company
    st.session_state["last_generated_paths"] = {
        "chunks": str(chunks_path),
        "package": str(package_path),
        "report": str(report_path),
    }
    st.success("Diligence package generated successfully.")
    st.rerun()

package_path = package_path_for_company(selected_company)
if not package_path.exists():
    st.info("No generated diligence package found yet for this company. Upload or use existing PDFs, then click Generate Diligence Package.")
    st.stop()

diligence_package = load_package(package_path)
sections = package_to_sections(diligence_package)
ordered = ordered_sections(sections)
source_doc_count = count_source_docs(diligence_package.get("source_documents"))

focus_section = st.sidebar.selectbox(
    "Focus section",
    ["Full report"] + [name for name, _ in ordered],
)

st.sidebar.header("Included Sections")
for name, _ in ordered:
    st.sidebar.markdown(f"- {name}")

last_generated_paths = st.session_state.get("last_generated_paths")
if last_generated_paths and st.session_state.get("last_generated_company") == selected_company:
    st.sidebar.header("Latest Output")
    st.sidebar.markdown(f"- Package: `{Path(last_generated_paths['package']).name}`")
    st.sidebar.markdown(f"- Report: `{Path(last_generated_paths['report']).name}`")

hero_left, hero_mid, hero_right = st.columns([3, 1, 1])
with hero_left:
    st.markdown(f"## {selected_company}")
    st.write(
        "This workspace is driven by the structured diligence package and is meant to feel closer to a PE / M&A workbench than a generic document chat tool."
    )
with hero_mid:
    st.metric("Sections", len(ordered))
with hero_right:
    st.metric("Source Docs", source_doc_count)

if focus_section == "Full report":
    for section_name, section_value in ordered:
        render_section(section_name, section_value)
        st.divider()
else:
    for section_name, section_value in ordered:
        if section_name == focus_section:
            render_section(section_name, section_value)
            break
