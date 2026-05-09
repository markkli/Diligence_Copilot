from pathlib import Path
import re

import streamlit as st


st.set_page_config(
    page_title="Diligence Workspace",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

REPORT_PATTERN = "*_diligence_report.md"
PRIMARY_ORDER = [
    "Commercial Diligence Memo",
    "Risk Dashboard",
    "Company Overview",
    "Investment Committee Summary",
    "Evidence Table",
    "Diligence Questions",
    "Source Documents",
]


def find_report_files():
    return sorted(Path(".").glob(REPORT_PATTERN))


def prettify_company_name(report_path: Path) -> str:
    name = report_path.stem.replace("_diligence_report", "")
    return name.replace("_", " ").title()


def load_report(report_path: Path) -> str:
    return report_path.read_text()


def split_markdown_sections(report_text: str):
    sections = {}
    current_section = None
    buffer = []

    for line in report_text.splitlines():
        if line.startswith("## "):
            if current_section is not None:
                sections[current_section] = "\n".join(buffer).strip()
            current_section = line.replace("## ", "", 1).strip()
            buffer = []
        elif not line.startswith("# "):
            buffer.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(buffer).strip()

    return {name: content for name, content in sections.items() if content}


def parse_source_documents(section_text: str):
    rows = []
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        clean_line = line[2:]
        if ": pages " in clean_line:
            document, pages = clean_line.split(": pages ", 1)
            rows.append((document.strip(), pages.strip()))
        else:
            rows.append((clean_line, ""))
    return rows


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


def render_source_documents(content: str):
    st.subheader("Source Documents")
    rows = parse_source_documents(content)
    if not rows:
        st.markdown(content)
        return

    cols = st.columns(2)
    for idx, (document, pages) in enumerate(rows):
        with cols[idx % 2]:
            st.markdown(f"**{document}**")
            st.caption(f"Pages: {pages}" if pages else "Pages not available")


def render_section(title: str, content: str):
    st.subheader(title)

    if title == "Source Documents":
        render_source_documents(content)
        return

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


report_files = find_report_files()

st.title("Diligence Workspace")
st.caption(
    "A first-pass commercial due diligence workspace that turns generated memo sections into a more readable analyst view."
)

if not report_files:
    st.error("No diligence report files were found in the project folder.")
    st.stop()

report_options = {prettify_company_name(path): path for path in report_files}
company_name = st.sidebar.selectbox("Company", list(report_options.keys()))
selected_report = report_options[company_name]
report_text = load_report(selected_report)
sections = split_markdown_sections(report_text)
ordered = ordered_sections(sections)
source_docs = parse_source_documents(sections.get("Source Documents", ""))

st.sidebar.header("Workspace")
st.sidebar.markdown(f"**Company:** {company_name}")
st.sidebar.markdown(f"**Report File:** `{selected_report.name}`")
focus_section = st.sidebar.selectbox(
    "Focus section",
    ["Full report"] + [name for name, _ in ordered],
)

st.sidebar.header("Included Sections")
for name, _ in ordered:
    st.sidebar.markdown(f"- {name}")

st.sidebar.header("Roadmap")
st.sidebar.caption("Uploads and live source search should be added after the current viewer feels solid.")

hero_left, hero_mid, hero_right = st.columns([3, 1, 1])
with hero_left:
    st.markdown(f"## {company_name}")
    st.write(
        "This workspace is driven by the MVP diligence package and is meant to feel closer to a structured PE / M&A workbench than a generic PDF chat tool."
    )
with hero_mid:
    st.metric("Sections", len(ordered))
with hero_right:
    st.metric("Source Docs", len(source_docs))

if focus_section == "Full report":
    for section_name, content in ordered:
        render_section(section_name, content)
        st.divider()
else:
    for section_name, content in ordered:
        if section_name == focus_section:
            render_section(section_name, content)
            break
