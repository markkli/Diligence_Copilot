from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader


MODEL_NAME = "gpt-5-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
SECTION_LABELS = {
    "company_overview": "Company Overview",
    "commercial_diligence_memo": "Commercial Diligence Memo",
    "investment_committee_summary": "Investment Committee Summary",
    "risk_dashboard": "Risk Dashboard",
    "evidence_table": "Evidence Table",
    "diligence_questions": "Diligence Questions",
    "source_documents": "Source Documents",
}


def slugify_company_name(company_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", company_name.lower()).strip("_")
    return slug or "company"


WORKFLOW_TO_PACKAGE_KEY = {
    "Risk Register": "risk_dashboard",
    "Investment Memo": "commercial_diligence_memo",
    "Management Questions": "diligence_questions",
    "Company Overview": "company_overview",
    "Investment Committee Summary": "investment_committee_summary",
    "Evidence Table": "evidence_table",
}


def get_client() -> OpenAI:
    load_dotenv()
    return OpenAI()


def extract_pdf_chunks(pdf_path: Path, max_chars: int = 3000, overlap: int = 300) -> list[dict[str, Any]]:
    reader = PdfReader(pdf_path)
    chunks: list[dict[str, Any]] = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        i = 0

        while i < len(text):
            chunk_text = text[i : i + max_chars]
            chunks.append(
                {
                    "file_name": pdf_path.name,
                    "page_number": page_num,
                    "text": chunk_text,
                }
            )
            i += max_chars - overlap

    return chunks


def build_chunks_for_company(company_folder: Path) -> list[dict[str, Any]]:
    pdf_files = sorted(company_folder.glob("*.pdf"))
    all_chunks: list[dict[str, Any]] = []
    for pdf_file in pdf_files:
        all_chunks.extend(extract_pdf_chunks(pdf_file))
    return all_chunks


def embed_chunks(chunks: list[dict[str, Any]], client: OpenAI | None = None) -> list[dict[str, Any]]:
    client = client or get_client()
    for chunk in chunks:
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=chunk["text"])
        chunk["embedding"] = response.data[0].embedding
    return chunks


def save_json(data: Any, path: Path) -> None:
    path.write_text(json.dumps(data, indent=1))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot_product / (norm_a * norm_b)


def search_chunks_by_embedding(
    chunks: list[dict[str, Any]], query: str, client: OpenAI | None = None, top_k: int = 5
) -> list[dict[str, Any]]:
    client = client or get_client()
    query_response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    query_embedding = query_response.data[0].embedding

    results: list[dict[str, Any]] = []
    for chunk in chunks:
        score = cosine_similarity(query_embedding, chunk["embedding"])
        results.append(
            {
                "file_name": chunk["file_name"],
                "page_number": chunk["page_number"],
                "text": chunk["text"],
                "score": score,
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def get_workflow_queries(company_name: str) -> dict[str, list[str]]:
    return {
        "Risk Register": [
            f"{company_name} risk factors competition customer concentration pricing pressure churn retention",
            f"{company_name} operational risk implementation cloud migration execution regulatory legal",
            f"{company_name} revenue margin growth slowdown contract renewal profitability demand uncertainty",
        ],
        "Investment Memo": [
            f"{company_name} company overview products customers revenue business model segments geography",
            f"{company_name} market growth drivers competition differentiation positioning",
            f"{company_name} risks opportunities strategy expansion profitability",
        ],
        "Management Questions": [
            f"{company_name} risk factors uncertainty assumptions execution issues customer concentration competition pricing",
            f"{company_name} growth slowdown profitability margin pressure contract renewal churn implementation",
            f"{company_name} market drivers regulatory risk cloud migration product adoption differentiation",
        ],
        "Company Overview": [
            f"{company_name} company overview products services customers business model value chain",
            f"{company_name} revenue segments geography end markets customer base pricing model",
            f"{company_name} InsuranceSuite InsuranceNow platform offerings operations market role",
        ],
        "Investment Committee Summary": [
            f"{company_name} investment thesis growth drivers competitive positioning why now opportunities",
            f"{company_name} downside risks customer concentration margin pressure cyclicality execution",
            f"{company_name} assumptions further diligence recommendation open questions",
        ],
        "Evidence Table": [
            f"{company_name} products customers business model revenue segments geography",
            f"{company_name} competition differentiation risks opportunities margin growth",
            f"{company_name} risk factors contradictions uncertainty management claims filings",
        ],
    }


def get_workflow_prompts(company_name: str) -> dict[str, str]:
    return {
        "Risk Register": f"""
You are producing a consulting-style risk register for {company_name}.

Use only the retrieved evidence provided below.
Do not hallucinate numbers, facts, or competitor details.
If a fact is not supported by the evidence, say "Not disclosed".
Keep the output concise, structured, and bullet-heavy.
Do not write long paragraphs.
Where documents suggest uncertainty, tension, or inconsistency, note that explicitly.

Output a ranked risk register.
For each risk, include exactly these fields:
- Risk Name
- Category (Market / Operational / Financial / Regulatory)
- Description
- Evidence
- Severity (High / Medium / Low)
- Confidence (High / Medium / Low)

Rules:
- Description should be 1-2 lines maximum.
- Evidence must cite the source using document name and page number.
- Severity should reflect potential business impact.
- Confidence should reflect how strongly the retrieved evidence supports the risk.
- Avoid duplicate risks; combine overlapping points when appropriate.
- Prioritize the most decision-relevant risks first.

Return only the final risk register.
""",
        "Investment Memo": f"""
You are producing a consulting-style investment memo for {company_name}.

Use only the retrieved evidence provided below.
Do not hallucinate numbers, facts, or competitor details.
If information is not supported by the evidence, say "Not disclosed".
Keep the output concise, structured, and bullet-heavy.
Do not write long paragraphs.
Where documents suggest uncertainty, contradiction, or tension, note that explicitly.
Prioritize decision-useful content over completeness.

Output EXACTLY in this format:

[Executive Summary]
- Company description
- Recommendation (Invest / Pass / Further Diligence)
- Top 3 reasons

[Business Model]
- Revenue streams
- Key segments
- Geography

[Market Overview]
- Market size (if available)
- Growth rate
- Key drivers

[Competitive Positioning]
- Key competitors
- Differentiation
- Positioning

[Key Risks]
- Ranked bullet list

[Upside Opportunities]
- Ranked bullet list

[Deal Verdict]
- Recommendation
- Top risks
- What needs further validation

Rules:
- Every important claim must be grounded in the retrieved evidence.
- Include source references using document name and page number where possible.
- If market size or growth rate is not disclosed, say "Not disclosed".
- Avoid generic private equity phrasing unless it is supported by evidence.
- Keep recommendations practical and evidence-based.
- Do not produce tables.
- Do not include anything outside the specified structure.

Return only the final investment memo.
""",
        "Management Questions": f"""
You are producing a consulting-style management question list for {company_name}.

Use only the retrieved evidence provided below.
Do not hallucinate facts or numbers.
If a point is not supported by evidence, do not use it.
Keep the output concise, structured, and bullet-heavy.
Do not write long paragraphs.
Focus on the most decision-relevant uncertainties, risks, assumptions, and gaps.

Generate 8-12 high-quality diligence questions.
These questions should be suitable for a PE / M&A commercial diligence process.
Do not generate generic management questions.

For each question, include exactly these fields:
- Question
- Why it matters
- Evidence prompting the question

Rules:
- Questions should focus on risks, weakly supported claims, contradictions, operational complexity, customer issues, competition, growth assumptions, profitability, and execution.
- Why it matters should be 1-2 lines maximum.
- Evidence prompting the question must cite document name and page number.
- Avoid duplicate or overlapping questions.
- Prioritize questions that could materially affect investment attractiveness or diligence conclusions.

Return only the final management question list.
""",
        "Company Overview": f"""
You are producing a consulting-style company overview for {company_name}.

Use only the retrieved evidence provided below.
Do not hallucinate facts, customer types, geography, or segment details.
If information is not supported by evidence, say "Not disclosed".
Keep the output concise, structured, and bullet-heavy.
Do not write long paragraphs.

Output EXACTLY in this format:

[Company Description]
- What the company does
- Products / services
- Position in the value chain

[Business Model]
- Revenue model
- Customer base
- Pricing / monetization approach

[Operating Footprint]
- Revenue segments
- Geography
- End markets

Rules:
- Every important claim must be grounded in the retrieved evidence.
- Include source references using document name and page number where possible.
- Use bullets only.
- If a section is not disclosed, say "Not disclosed".

Return only the final company overview.
""",
        "Investment Committee Summary": f"""
You are producing an investment committee-style summary for {company_name}.

Use only the retrieved evidence provided below.
Do not hallucinate facts, numbers, or competitor details.
If information is not supported by evidence, say "Not disclosed".
Keep the output concise, structured, and decision-oriented.
Do not write long paragraphs.
Highlight uncertainty, contradictions, and open validation points explicitly.

Output EXACTLY in this format:

[Investment Thesis]
- Core thesis
- Why now

[Upside Case]
- Main upside drivers

[Downside Case]
- Main downside risks

[Key Assumptions]
- Bullet list

[Open Diligence Questions]
- Bullet list

[Preliminary Recommendation]
- Invest / Pass / Further Diligence
- One short explanation

Rules:
- Every important claim must be grounded in the retrieved evidence.
- Include source references using document name and page number where possible.
- Avoid generic investment language unless supported by evidence.
- Keep the recommendation neutral if evidence is mixed or incomplete.

Return only the final investment committee summary.
""",
        "Evidence Table": f"""
You are producing an evidence-backed claims table for {company_name}.

Use only the retrieved evidence provided below.
Do not hallucinate claims or numbers.
Keep the output concise and structured.
Focus on the most important commercial diligence claims, not every minor fact.

Output a structured bullet list. For each item include exactly these fields:
- Claim
- Support Level (High / Medium / Low)
- Document
- Page
- Evidence Snippet
- Notes

Rules:
- Claims should cover topics such as business model, customers, competition, risks, growth, margins, and opportunities where supported.
- Evidence Snippet should be short and specific, not a long paragraph.
- Notes can mention uncertainty, contradiction, or missing context.
- If support is weak, mark Support Level accordingly.
- Avoid duplicate claims.

Return only the final evidence table.
""",
    }


def gather_workflow_evidence(
    chunks: list[dict[str, Any]],
    workflow_name: str,
    company_name: str,
    client: OpenAI | None = None,
    top_k_per_query: int = 5,
    min_per_query: int = 2,
    max_context_chunks: int = 12,
) -> dict[str, Any]:
    workflow_queries = get_workflow_queries(company_name).get(workflow_name, [])
    if len(workflow_queries) * min_per_query > max_context_chunks:
        raise ValueError("min_per_query is too large for max_context_chunks")

    per_query_results: list[list[dict[str, Any]]] = []
    for query in workflow_queries:
        results = search_chunks_by_embedding(chunks, query, client=client, top_k=top_k_per_query)
        per_query_results.append(results)

    deduped: dict[tuple[str, int, str], dict[str, Any]] = {}
    selected: list[dict[str, Any]] = []

    for results in per_query_results:
        count = 0
        for result in results:
            key = (result["file_name"], result["page_number"], result["text"])
            if key not in deduped:
                deduped[key] = result
                selected.append(result)
                count += 1
            if count >= min_per_query:
                break

    leftovers: list[dict[str, Any]] = []
    for results in per_query_results:
        for result in results:
            key = (result["file_name"], result["page_number"], result["text"])
            if key not in deduped:
                leftovers.append(result)

    leftovers.sort(key=lambda x: x["score"], reverse=True)

    for result in leftovers:
        if len(selected) >= max_context_chunks:
            break
        key = (result["file_name"], result["page_number"], result["text"])
        if key not in deduped:
            deduped[key] = result
            selected.append(result)

    selected.sort(key=lambda x: x["score"], reverse=True)
    return {"workflow": workflow_name, "queries": workflow_queries, "results": selected}


def build_context(results: list[dict[str, Any]], max_chars: int = 18000) -> str:
    context = ""
    for result in results:
        entry = f"File: {result['file_name']}, Page: {result['page_number']}\n{result['text']}\n\n"
        if len(context) + len(entry) > max_chars:
            break
        context += entry
    return context


def run_workflow(
    chunks: list[dict[str, Any]],
    workflow_name: str,
    company_name: str,
    client: OpenAI | None = None,
) -> dict[str, Any]:
    client = client or get_client()
    evidence = gather_workflow_evidence(chunks, workflow_name, company_name, client=client)
    context = build_context(evidence["results"])
    prompt = get_workflow_prompts(company_name).get(workflow_name, "")
    full_prompt = f"""
INSTRUCTIONS:
{prompt}

CONTEXT:
{context}
"""
    response = client.responses.create(model=MODEL_NAME, input=full_prompt)
    return {
        "workflow_name": workflow_name,
        "queries": evidence["queries"],
        "results": evidence["results"],
        "context": context,
        "output": response.output_text,
    }


def build_source_documents(diligence_package: dict[str, Any]) -> list[dict[str, Any]]:
    source_documents: dict[str, set[int]] = {}
    for section_value in diligence_package.values():
        if section_value is None or not isinstance(section_value, dict) or "results" not in section_value:
            continue
        for result in section_value["results"]:
            document = result["file_name"]
            page = result["page_number"]
            source_documents.setdefault(document, set()).add(page)
    return [
        {"document": doc, "pages": sorted(list(pages))}
        for doc, pages in source_documents.items()
    ]


def build_diligence_package(company_name: str, chunks: list[dict[str, Any]], client: OpenAI | None = None) -> dict[str, Any]:
    client = client or get_client()
    package = {
        "company_overview": None,
        "commercial_diligence_memo": None,
        "investment_committee_summary": None,
        "risk_dashboard": None,
        "evidence_table": None,
        "diligence_questions": None,
        "source_documents": None,
    }

    for workflow_name, package_key in WORKFLOW_TO_PACKAGE_KEY.items():
        result = run_workflow(chunks, workflow_name, company_name, client=client)
        package[package_key] = {
            "output": result["output"],
            "queries": result["queries"],
            "results": result["results"],
            "context": result["context"],
        }

    package["source_documents"] = build_source_documents(package)
    return package


def render_section_value(section_value: Any) -> str:
    if section_value is None:
        return "Not generated yet"
    if isinstance(section_value, dict) and "output" in section_value:
        return section_value["output"]
    if isinstance(section_value, list):
        if not section_value:
            return "Not generated yet"
        if all(isinstance(item, dict) and "document" in item and "pages" in item for item in section_value):
            return "\n".join(
                f"- {item['document']}: pages {', '.join(str(page) for page in item['pages'])}"
                for item in section_value
            )
    return str(section_value)


def render_markdown_report(company_name: str, diligence_package: dict[str, Any]) -> str:
    return f"""
# Diligence Report: {company_name}

## Commercial Diligence Memo
{render_section_value(diligence_package['commercial_diligence_memo'])}

## Risk Dashboard
{render_section_value(diligence_package['risk_dashboard'])}

## Company Overview
{render_section_value(diligence_package['company_overview'])}

## Investment Committee Summary
{render_section_value(diligence_package['investment_committee_summary'])}

## Evidence Table
{render_section_value(diligence_package['evidence_table'])}

## Diligence Questions
{render_section_value(diligence_package['diligence_questions'])}

## Source Documents
{render_section_value(diligence_package['source_documents'])}
""".strip() + "\n"


def package_file_path(base_dir: Path, company_name: str) -> Path:
    return base_dir / f"{slugify_company_name(company_name)}_diligence_package.json"


def report_file_path(base_dir: Path, company_name: str) -> Path:
    return base_dir / f"{slugify_company_name(company_name)}_diligence_report.md"


def chunks_file_path(base_dir: Path, company_name: str) -> Path:
    return base_dir / f"{slugify_company_name(company_name)}_chunks.json"


def save_package_outputs(base_dir: Path, company_name: str, package: dict[str, Any]) -> tuple[Path, Path]:
    package_path = package_file_path(base_dir, company_name)
    report_path = report_file_path(base_dir, company_name)
    save_json(package, package_path)
    report_path.write_text(render_markdown_report(company_name, package))
    return package_path, report_path


def generate_company_outputs(
    company_name: str,
    company_folder: Path,
    base_dir: Path,
    client: OpenAI | None = None,
) -> tuple[dict[str, Any], Path, Path, Path]:
    client = client or get_client()
    chunks = build_chunks_for_company(company_folder)
    embed_chunks(chunks, client=client)
    chunks_path = chunks_file_path(base_dir, company_name)
    save_json(chunks, chunks_path)
    package = build_diligence_package(company_name, chunks, client=client)
    package_path, report_path = save_package_outputs(base_dir, company_name, package)
    return package, chunks_path, package_path, report_path
