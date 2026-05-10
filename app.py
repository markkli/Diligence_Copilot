from pathlib import Path
import json
import re

import streamlit as st


st.set_page_config(
    page_title="Diligence Workspace",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

PACKAGE_PATTERN = "*_diligence_package.json"
DEFAULT_PACKAGE = "diligence_package.json"
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
    matches = sorted(Path(".").glob(PACKAGE_PATTERN))
    default_path = Path(DEFAULT_PACKAGE)
    if default_path.exists() and default_path not in matches:
        matches.append(default_path)
    return matches


def prettify_company_name(package_path: Path) -> str:
    name = package_path.stem.replace("_diligence_package", "")
    if name == "diligence_package":
        return "Current Company"
    return name.replace("_", " ").title()


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


package_files = find_package_files()

st.title("Diligence Workspace")
st.caption(
    "A first-pass commercial due diligence workspace that renders structured package outputs instead of raw notebook text."
)

if not package_files:
    st.error("No diligence package JSON files were found in the project folder.")
    st.stop()

package_options = {prettify_company_name(path): path for path in package_files}
company_name = st.sidebar.selectbox("Company", list(package_options.keys()))
selected_package = package_options[company_name]
diligence_package = load_package(selected_package)
sections = package_to_sections(diligence_package)
ordered = ordered_sections(sections)
source_doc_count = count_source_docs(diligence_package.get("source_documents"))

st.sidebar.header("Workspace")
st.sidebar.markdown(f"**Company:** {company_name}")
st.sidebar.markdown(f"**Package File:** `{selected_package.name}`")
focus_section = st.sidebar.selectbox(
    "Focus section",
    ["Full report"] + [name for name, _ in ordered],
)

st.sidebar.header("Included Sections")
for name, _ in ordered:
    st.sidebar.markdown(f"- {name}")

st.sidebar.header("Roadmap")
st.sidebar.caption("Next likely product steps: uploads, regeneration, live/public-source ingestion, and charts from structured package fields.")

hero_left, hero_mid, hero_right = st.columns([3, 1, 1])
with hero_left:
    st.markdown(f"## {company_name}")
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
