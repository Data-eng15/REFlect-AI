from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .models import AgentState, AgentStatus, EvidenceItem, ImpactSection, PaperMetadata, TraceLog
from .rag import index_and_retrieve
from .hf_synthesis import hf_synthesizer


DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._();/:A-Z0-9]+", re.IGNORECASE)
GENERIC_TITLE_TERMS = {
    "deep",
    "learning",
    "machine",
    "analysis",
    "survey",
    "review",
    "introduction",
    "method",
    "methods",
    "model",
    "models",
    "data",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(agent: str, message: str, **data: Any) -> TraceLog:
    return TraceLog(timestamp=now_iso(), agent=agent, message=message, data=data)


def status(name: str, label: str, state: AgentState, detail: str) -> AgentStatus:
    return AgentStatus(name=name, label=label, state=state, detail=detail)


def normalize_query(query: str) -> str:
    return query.strip()


def extract_doi(query: str) -> str | None:
    match = DOI_PATTERN.search(query)
    return match.group(0) if match else None


def meaningful_title_terms(title: str) -> list[str]:
    return [
        term
        for term in re.findall(r"[a-z0-9]+", title.lower())
        if len(term) > 3 and term not in GENERIC_TITLE_TERMS
    ]


def authors_from_crossref(work: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    for author in work.get("author", [])[:8]:
        given = author.get("given", "")
        family = author.get("family", "")
        name = " ".join(part for part in [given, family] if part).strip()
        if name:
            authors.append(name)
    return authors


def year_from_crossref(work: dict[str, Any]) -> int | None:
    parts = work.get("published-print", {}).get("date-parts") or work.get("published-online", {}).get("date-parts") or work.get("created", {}).get("date-parts")
    try:
        return int(parts[0][0])
    except Exception:
        return None


async def fetch_crossref(client: httpx.AsyncClient, query: str) -> tuple[PaperMetadata | None, list[TraceLog]]:
    logs = [log("Metadata", "Resolving input with CrossRef")]
    doi = extract_doi(query)
    try:
        if doi:
            url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
            response = await client.get(url, timeout=12)
            response.raise_for_status()
            work = response.json()["message"]
        else:
            url = "https://api.crossref.org/works"
            response = await client.get(url, params={"query.title": query, "rows": 1}, timeout=12)
            response.raise_for_status()
            items = response.json()["message"].get("items", [])
            if not items:
                logs.append(log("Metadata", "No CrossRef match found"))
                return None, logs
            work = items[0]

        title = (work.get("title") or ["Unknown title"])[0]
        metadata = PaperMetadata(
            title=title,
            authors=authors_from_crossref(work),
            year=year_from_crossref(work),
            doi=work.get("DOI"),
            abstract=clean_abstract(work.get("abstract")),
            source_url=work.get("URL"),
        )
        logs.append(log("Metadata", "Metadata resolved", title=metadata.title, doi=metadata.doi))
        return metadata, logs
    except Exception as exc:
        logs.append(log("Metadata", "CrossRef lookup failed", error=str(exc)))
        return None, logs


def clean_abstract(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"<[^>]+>", "", value).strip()


def inverted_abstract_to_text(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for position in positions:
            words.append((position, word))
    return " ".join(word for _, word in sorted(words))[:900]


async def fetch_semantic_scholar(client: httpx.AsyncClient, metadata: PaperMetadata, original_query: str) -> tuple[int, list[EvidenceItem], list[TraceLog]]:
    logs = [log("Scholar", "Querying Semantic Scholar Academic Graph")]
    paper_id = metadata.doi or extract_doi(original_query) or original_query
    fields = "title,year,authors,citationCount,url,abstract,citations.title,citations.year,citations.authors,citations.url,citations.abstract,citations.citationCount"
    headers = {}
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
        headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]

    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/{quote(paper_id, safe='')}"
        response = await client.get(url, params={"fields": fields}, headers=headers, timeout=15)
        response.raise_for_status()
        payload = response.json()
        citations = payload.get("citations", [])[:20]
        evidence = [
            EvidenceItem(
                title=item.get("title") or "Untitled citing paper",
                url=item.get("url"),
                year=item.get("year"),
                authors=[author.get("name", "") for author in item.get("authors", [])[:5] if author.get("name")],
                snippet=item.get("abstract"),
                source="Semantic Scholar",
                kind="citation",
                citation_count=item.get("citationCount"),
            )
            for item in citations
            if item.get("title")
        ]
        count = int(payload.get("citationCount") or len(evidence))
        logs.append(log("Scholar", "Citation data retrieved", citation_count=count, evidence_items=len(evidence)))
        return count, evidence, logs
    except Exception as exc:
        logs.append(log("Scholar", "Semantic Scholar lookup failed", error=str(exc)))
        return 0, [], logs


async def fetch_openalex_fallback(client: httpx.AsyncClient, query: str) -> tuple[int, list[EvidenceItem], list[TraceLog]]:
    logs = [log("Fallback", "Searching OpenAlex for additional evidence")]
    try:
        response = await client.get("https://api.openalex.org/works", params={"search": query, "per-page": 8}, timeout=12)
        response.raise_for_status()
        results = response.json().get("results", [])
        evidence = []
        for item in results:
            evidence.append(
                EvidenceItem(
                    title=item.get("display_name") or "Untitled work",
                    url=item.get("doi") or item.get("id"),
                    year=item.get("publication_year"),
                    authors=[a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])[:5] if a.get("author", {}).get("display_name")],
                    snippet=inverted_abstract_to_text(item.get("abstract_inverted_index")),
                    source="OpenAlex",
                    kind="citation",
                    citation_count=item.get("cited_by_count"),
                    metric_label="Citations",
                    metric_value=f"{item.get('cited_by_count'):,}" if item.get("cited_by_count") is not None else None,
                )
            )
        citation_count = int(results[0].get("cited_by_count") or 0) if results else 0
        logs.append(log("Fallback", "OpenAlex evidence retrieved", evidence_items=len(evidence), citation_count=citation_count))
        return citation_count, evidence, logs
    except Exception as exc:
        logs.append(log("Fallback", "OpenAlex fallback failed", error=str(exc)))
        return 0, [], logs


async def fetch_openalex_enrichment(client: httpx.AsyncClient, metadata: PaperMetadata) -> tuple[list[EvidenceItem], list[str], list[TraceLog]]:
    logs = [log("Content", "Inspecting OpenAlex for topics, funders, and open-access links")]
    if not metadata.doi and not metadata.title:
        logs.append(log("Content", "Skipped OpenAlex enrichment; no DOI or title"))
        return [], [], logs

    try:
        if metadata.doi:
            response = await client.get(f"https://api.openalex.org/works/doi:{quote(metadata.doi, safe='')}", timeout=12)
        else:
            response = await client.get("https://api.openalex.org/works", params={"search": metadata.title, "per-page": 1}, timeout=12)
        response.raise_for_status()
        payload = response.json()
        work = payload.get("results", [payload])[0] if "results" in payload else payload
        evidence: list[EvidenceItem] = []

        for location_name in ["best_oa_location", "primary_location"]:
            location = work.get(location_name) or {}
            landing_url = location.get("landing_page_url")
            pdf_url = location.get("pdf_url")
            if landing_url or pdf_url:
                source = location.get("source", {}) or {}
                evidence.append(
                    EvidenceItem(
                        title=f"{metadata.title} source record",
                        url=pdf_url or landing_url,
                        year=metadata.year,
                        authors=metadata.authors[:5],
                        snippet="OpenAlex located a landing page or full-text route for this work.",
                        source=source.get("display_name") or "OpenAlex",
                        kind="full_text",
                        metric_label="Access",
                        metric_value="PDF" if pdf_url else "Landing page",
                    )
                )

        for funder in (work.get("funders") or [])[:5]:
            name = funder.get("display_name")
            if name:
                evidence.append(
                    EvidenceItem(
                        title=name,
                        url=funder.get("id"),
                        year=metadata.year,
                        snippet="OpenAlex links this work to a funder record.",
                        source="OpenAlex",
                        kind="funding",
                    )
                )

        topics = [
            topic.get("display_name")
            for topic in (work.get("topics") or [])[:6]
            if topic.get("display_name")
        ]
        if work.get("primary_topic", {}).get("display_name"):
            topics.insert(0, work["primary_topic"]["display_name"])
        topics = list(dict.fromkeys(topics))[:6]
        logs.append(log("Content", "OpenAlex enrichment complete", topics=len(topics), evidence_items=len(evidence)))
        return evidence, topics, logs
    except Exception as exc:
        logs.append(log("Content", "OpenAlex enrichment failed", error=str(exc)))
        return [], [], logs


async def fetch_github_adoption(client: httpx.AsyncClient, metadata: PaperMetadata) -> tuple[list[EvidenceItem], list[TraceLog]]:
    logs = [log("Code", "Searching GitHub repositories for adoption signals")]
    title = metadata.title.strip()
    if not title or title == "Unknown title":
        logs.append(log("Code", "Skipped GitHub search; no reliable title"))
        return [], logs

    title_terms = meaningful_title_terms(title)
    if len(title_terms) < 2:
        logs.append(log("Code", "Skipped GitHub search; title is too generic for reliable repository matching", title=title))
        return [], logs

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

    quoted_title = f'"{title[:80]}"'
    query = f"{quoted_title} in:name,description,readme"
    try:
        response = await client.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 6},
            headers=headers,
            timeout=12,
        )
        response.raise_for_status()
        repos = response.json().get("items", [])
        evidence = []
        for repo in repos:
            evidence.append(
                EvidenceItem(
                    title=repo.get("full_name") or repo.get("name") or "GitHub repository",
                    url=repo.get("html_url"),
                    year=None,
                    authors=[repo.get("owner", {}).get("login", "")] if repo.get("owner", {}).get("login") else [],
                    snippet=repo.get("description") or "Repository matched distinctive title terms from the paper.",
                    source="GitHub",
                    kind="code",
                    metric_label="Stars",
                    metric_value=f"{repo.get('stargazers_count', 0):,}",
                )
            )
        logs.append(log("Code", "GitHub adoption search complete", repositories=len(evidence)))
        return evidence, logs
    except Exception as exc:
        logs.append(log("Code", "GitHub adoption search failed", error=str(exc)))
        return [], logs


async def fetch_google_patents(client: httpx.AsyncClient, metadata: PaperMetadata) -> tuple[list[EvidenceItem], list[TraceLog]]:
    logs = [log("Patents", "Searching Google Patents via XHR API")]
    title = metadata.title.strip()
    if not title or title == "Unknown title":
        logs.append(log("Patents", "Skipped patent search; no reliable title"))
        return [], logs

    query = quote(f'"{title[:80]}"', safe="")
    url = f"https://patents.google.com/xhr/query?url=q%3D{query}"
    try:
        response = await client.get(url, timeout=15)
        response.raise_for_status()
        payload = response.json()
        
        cluster = payload.get("results", {}).get("cluster", [])
        if not cluster:
            logs.append(log("Patents", "No patent matches found"))
            return [], logs

        results = cluster[0].get("result", [])
        evidence = []
        for res in results[:5]:
            patent_info = res.get("patent", {})
            pub_num = patent_info.get("publication_number", "Unknown")
            patent_title = patent_info.get("title", f"Patent {pub_num}")
            patent_title = re.sub(r"<[^>]+>", "", patent_title).strip()
            snippet = re.sub(r"<[^>]+>", "", patent_info.get("snippet", "")).strip()
            assignee = patent_info.get("assignee", "")
            inventor = patent_info.get("inventor", "")
            
            authors = []
            if assignee: authors.append(assignee)
            elif inventor: authors.append(inventor)
            
            year_str = patent_info.get("publication_date", "")
            year = int(year_str[:4]) if len(year_str) >= 4 and year_str[:4].isdigit() else None
            
            evidence.append(
                EvidenceItem(
                    title=f"[{pub_num}] {patent_title}",
                    url=f"https://patents.google.com/patent/{pub_num}/en",
                    year=year,
                    authors=authors,
                    snippet=snippet,
                    source="Google Patents",
                    kind="patent",
                    metric_label="Assignee" if assignee else None,
                    metric_value=assignee[:25] if assignee else None,
                )
            )
        
        logs.append(log("Patents", "Google Patents search complete", records=len(evidence)))
        return evidence, logs
    except Exception as exc:
        logs.append(log("Patents", "Google Patents search failed", error=str(exc)))
        return [], logs


def synthesize(
    metadata: PaperMetadata,
    citation_count: int,
    evidence: list[EvidenceItem],
    topics: list[str],
    rag_contexts: list[str],
) -> tuple[str, list[ImpactSection], float, list[str], list[TraceLog], str, str]:
    logs = [log("Synthesis", "Generating evidence-grounded summary")]
    title = metadata.title
    year = metadata.year or "unknown year"
    authors = ", ".join(metadata.authors[:3]) if metadata.authors else "the authors"
    evidence_titles = [item.title for item in evidence[:4]]
    code_count = len([item for item in evidence if item.kind == "code"])
    full_text_count = len([item for item in evidence if item.kind == "full_text"])
    funding_count = len([item for item in evidence if item.kind == "funding"])
    citation_phrase = f"{citation_count:,} citations" if citation_count else "available citation evidence"

    if evidence_titles:
        evidence_sentence = "Citing work includes " + "; ".join(evidence_titles[:3]) + "."
    else:
        evidence_sentence = "The current run found limited downstream evidence, so the summary should be treated as preliminary."

    hf_summary, model_provider, hf_logs = hf_synthesizer.generate(metadata, citation_count, evidence, topics, rag_contexts)
    logs.extend(hf_logs)

    deterministic_summary = (
        f"{title} ({year}) by {authors} appears to have influenced later research through {citation_phrase}. "
        f"The strongest available evidence comes from retrieved citation records and metadata, which indicate downstream use, comparison, or extension of the work. "
        f"{evidence_sentence} The system has preserved source links so each claim can be checked before academic use."
    )
    summary = hf_summary or deterministic_summary

    sections = [
        ImpactSection(
            title="Research Influence",
            body=f"The paper is represented in citation databases with {citation_phrase}. The retrieved citing papers provide the first evidence layer for analysing how later authors position the work. The RAG layer retrieved {len(rag_contexts)} vector-memory chunks for synthesis.",
        ),
        ImpactSection(
            title="Applications",
            body=(
                "Likely application areas are inferred from OpenAlex topic metadata and citing-paper evidence. "
                + (f"Detected topics include {', '.join(topics[:5])}." if topics else "No topic labels were available for this paper yet.")
            ),
        ),
        ImpactSection(
            title="Technical Adoption",
            body=(
                f"The GitHub agent found {code_count} repository matches for adoption or implementation signals. "
                "These are search-based leads and should be verified before being counted as confirmed implementations."
            ),
        ),
        ImpactSection(
            title="Access & Funding",
            body=(
                f"The content agent found {full_text_count} source or full-text routes and {funding_count} funder signals. "
                "This helps distinguish citation influence from practical access and funding context."
            ),
        ),
    ]
    slm_faithfulness, judge_logs = hf_synthesizer.evaluate_faithfulness(summary, evidence, rag_contexts)
    logs.extend(judge_logs)

    if slm_faithfulness >= 0.0:
        faithfulness = slm_faithfulness
    else:
        faithfulness = score_faithfulness(summary, evidence, rag_contexts, citation_count, topics)
        
    guardrail_status = "passed" if faithfulness >= 0.75 else "review"
    limitations = []
    if not evidence:
        limitations.append("No citation evidence was retrieved from the available public APIs for this query.")
    if model_provider == "deterministic":
        limitations.append("AI narrative unavailable. Add GOOGLE_API_KEY to backend/.env for Gemini-powered summaries.")
        
    logs.append(log("Guardrail", "Faithfulness guardrail evaluated summary", faithfulness_score=faithfulness, status=guardrail_status))
    logs.append(log("Synthesis", "Summary generated", faithfulness_score=faithfulness, model_provider=model_provider))
    return summary, sections, faithfulness, limitations, logs, model_provider, guardrail_status


def score_faithfulness(summary: str, evidence: list[EvidenceItem], rag_contexts: list[str], citation_count: int, topics: list[str]) -> float:
    if not evidence:
        return 0.38
    evidence_text = " ".join([item.title + " " + (item.snippet or "") for item in evidence] + rag_contexts).lower()
    summary_terms = [term for term in re.findall(r"[a-z0-9]+", summary.lower()) if len(term) > 4]
    if not summary_terms:
        return 0.45
    overlap = sum(1 for term in summary_terms if term in evidence_text) / len(summary_terms)
    score = 0.45 + min(0.3, overlap * 0.35) + (0.08 if citation_count else 0) + (0.07 if rag_contexts else 0) + (0.04 if topics else 0)
    return round(min(0.91, score), 2)


class AnalysisState(TypedDict, total=False):
    query: str
    metadata: PaperMetadata
    citation_count: int
    topics: list[str]
    evidence: list[EvidenceItem]
    statuses: list[AgentStatus]
    logs: list[TraceLog]
    summary: str
    sections: list[ImpactSection]
    faithfulness: float
    limitations: list[str]
    rag_contexts: list[str]
    embedding_provider: str
    model_provider: str
    guardrail_status: str
    ref_report: str


def initial_statuses() -> list[AgentStatus]:
    return [
        status("metadata", "Metadata", AgentState.running, "Resolving paper identity"),
        status("scholar", "Scholar", AgentState.pending, "Waiting for metadata"),
        status("content", "Content", AgentState.pending, "Waiting for metadata"),
        status("code", "Code", AgentState.pending, "Waiting for metadata"),
        status("rag", "RAG", AgentState.pending, "Waiting for evidence"),
        status("impact", "Impact", AgentState.pending, "Waiting for retrieval"),
        status("synthesis", "Synthesis", AgentState.pending, "Waiting for evidence"),
        status("ref", "REF Report", AgentState.pending, "Waiting for synthesis"),
    ]


async def metadata_node(state: AnalysisState) -> AnalysisState:
    normalized = state["query"]
    logs = state["logs"]
    statuses = state["statuses"]
    async with httpx.AsyncClient(headers={"User-Agent": "ResearchImpactSummariser/0.1 (mailto:student@example.com)"}) as client:
        metadata, crossref_logs = await fetch_crossref(client, normalized)
    logs.extend(crossref_logs)
    if metadata is None:
        metadata = PaperMetadata(title=normalized, source_url=None)
        statuses[0] = status("metadata", "Metadata", AgentState.warning, "Used raw input as title")
    else:
        statuses[0] = status("metadata", "Metadata", AgentState.complete, "Paper metadata resolved")
    return {**state, "metadata": metadata, "statuses": statuses, "logs": logs}


async def retrieval_node(state: AnalysisState) -> AnalysisState:
    metadata = state["metadata"]
    normalized = state["query"]
    logs = state["logs"]
    statuses = state["statuses"]
    statuses[1] = status("scholar", "Scholar", AgentState.running, "Retrieving citations")
    statuses[2] = status("content", "Content", AgentState.running, "Finding full text and topics")
    statuses[3] = status("code", "Code", AgentState.running, "Searching repositories")
    async with httpx.AsyncClient(headers={"User-Agent": "ResearchImpactSummariser/0.1 (mailto:student@example.com)"}) as client:
        scholar_task = fetch_semantic_scholar(client, metadata, normalized)
        fallback_task = fetch_openalex_fallback(client, metadata.title)
        enrichment_task = fetch_openalex_enrichment(client, metadata)
        github_task = fetch_github_adoption(client, metadata)
        patent_task = fetch_google_patents(client, metadata)
        (citation_count, scholar_evidence, scholar_logs), (fallback_count, fallback_evidence, fallback_logs), (content_evidence, topics, content_logs), (code_evidence, code_logs), (patent_evidence, patent_logs) = await asyncio.gather(
            scholar_task, fallback_task, enrichment_task, github_task, patent_task
        )
    citation_count = citation_count or fallback_count
    logs.extend(scholar_logs + fallback_logs + content_logs + code_logs + patent_logs)
    evidence = dedupe_evidence(scholar_evidence + fallback_evidence + content_evidence + code_evidence + patent_evidence)
    statuses[1] = status("scholar", "Scholar", AgentState.complete if evidence else AgentState.warning, f"{len(evidence)} evidence items retrieved")
    statuses[2] = status("content", "Content", AgentState.complete if content_evidence or topics else AgentState.warning, f"{len(topics)} topics, {len(content_evidence)} links")
    statuses[3] = status("code", "Code", AgentState.complete if code_evidence else AgentState.warning, f"{len(code_evidence)} repository leads")
    statuses[5] = status("impact", "Impact", AgentState.complete, "Patent search lead prepared")
    return {**state, "citation_count": citation_count, "evidence": evidence, "topics": topics, "statuses": statuses, "logs": logs}


async def rag_node(state: AnalysisState) -> AnalysisState:
    logs = state["logs"]
    statuses = state["statuses"]
    statuses[4] = status("rag", "RAG", AgentState.running, "Embedding evidence")
    rag_contexts, embedding_provider, rag_logs = await asyncio.to_thread(index_and_retrieve, state["metadata"], state["evidence"], state["topics"])
    logs.extend(rag_logs)
    statuses[4] = status("rag", "RAG", AgentState.complete if rag_contexts else AgentState.warning, f"{len(rag_contexts)} context chunks")
    return {**state, "rag_contexts": rag_contexts, "embedding_provider": embedding_provider, "statuses": statuses, "logs": logs}


async def synthesis_node(state: AnalysisState) -> AnalysisState:
    logs = state["logs"]
    statuses = state["statuses"]
    statuses[6] = status("synthesis", "Synthesis", AgentState.running, "Synthesizing summary")
    summary, sections, faithfulness, limitations, synth_logs, model_provider, guardrail_status = await asyncio.to_thread(
        synthesize,
        state["metadata"],
        state["citation_count"],
        state["evidence"],
        state["topics"],
        state["rag_contexts"],
    )
    logs.extend(synth_logs)
    statuses[6] = status("synthesis", "Synthesis", AgentState.complete, "Summary ready")
    logs.append(log("Supervisor", "Analysis complete"))
    return {
        **state,
        "summary": summary,
        "sections": sections,
        "faithfulness": faithfulness,
        "limitations": limitations,
        "logs": logs,
        "statuses": statuses,
        "model_provider": model_provider,
        "guardrail_status": guardrail_status,
    }


async def ref_node(state: AnalysisState) -> AnalysisState:
    logs = state["logs"]
    statuses = state["statuses"]
    statuses[7] = status("ref", "REF Report", AgentState.running, "Drafting case study")
    
    # Try generating with HF
    hf_report, ref_logs = await asyncio.to_thread(
        hf_synthesizer.generate_ref_report,
        state["metadata"],
        state["evidence"],
        state["summary"],
        state["topics"]
    )
    logs.extend(ref_logs)
    
    # Fallback to deterministic template if HF fails or is disabled
    if not hf_report:
        title = state["metadata"].title
        authors = ", ".join(state["metadata"].authors) if state["metadata"].authors else "Unknown authors"
        year = state["metadata"].year or "Unknown year"
        citation_phrase = f"{state['citation_count']} citations" if state["citation_count"] else "limited citation data"
        
        evidence_list = "\n".join(f"- **{item.kind.title()}**: {item.title} ({item.source})" for item in state["evidence"][:5])
        if not evidence_list:
            evidence_list = "- No robust downstream evidence retrieved yet."
            
        hf_report = f"""### 1. Summary of Impact
The research titled "{title}" ({year}) has demonstrated clear downstream impact, primarily evidenced through its {citation_phrase}.

### 2. Underpinning Research
This research was conducted by {authors}. The system retrieved metadata and citation records confirming its status as a foundational or actively cited work within its domain.

### 3. Details of Impact
The impact of this work spans several domains, evidenced by the following adoption signals:
{evidence_list}

### 4. References to the Research
- CrossRef DOI: {state["metadata"].doi or "N/A"}
- {state["citation_count"]} downstream citations identified via Semantic Scholar and OpenAlex.
"""
        logs.append(log("REF", "Generated deterministic REF report template fallback"))

    statuses[7] = status("ref", "REF Report", AgentState.complete, "Report generated")
    return {**state, "ref_report": hf_report, "statuses": statuses, "logs": logs}


def build_graph():
    graph = StateGraph(AnalysisState)
    graph.add_node("metadata", metadata_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("rag", rag_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_node("ref_report", ref_node)
    graph.add_edge(START, "metadata")
    graph.add_edge("metadata", "retrieval")
    graph.add_edge("retrieval", "rag")
    graph.add_edge("rag", "synthesis")
    graph.add_edge("synthesis", "ref_report")
    graph.add_edge("ref_report", END)
    return graph.compile()


analysis_graph = build_graph()


async def analyze_paper(query: str):
    normalized = normalize_query(query)
    state = await analysis_graph.ainvoke(
        {
            "query": normalized,
            "statuses": initial_statuses(),
            "logs": [log("Supervisor", "LangGraph analysis started", query=normalized)],
            "citation_count": 0,
            "topics": [],
            "evidence": [],
            "rag_contexts": [],
            "embedding_provider": "not_run",
            "model_provider": "not_run",
            "guardrail_status": "not_run",
            "limitations": [],
            "ref_report": "",
        }
    )
    return {
        "metadata": state["metadata"],
        "summary": state["summary"],
        "sections": state["sections"],
        "evidence": state["evidence"][:32],
        "agent_statuses": state["statuses"],
        "logs": state["logs"],
        "faithfulness_score": state["faithfulness"],
        "citation_count": state["citation_count"],
        "topics": state["topics"],
        "model_provider": state["model_provider"],
        "rag_context_count": len(state["rag_contexts"]),
        "guardrail_status": state["guardrail_status"],
        "limitations": state["limitations"],
        "ref_report": state.get("ref_report", ""),
    }


def dedupe_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
    seen: set[str] = set()
    unique: list[EvidenceItem] = []
    for item in items:
        key = (item.url or item.title).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
