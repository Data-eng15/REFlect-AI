from __future__ import annotations
import json, re
from typing import Any
import asyncio
from .hf_synthesis import _call

_WRITER_SYSTEM = """You are a senior research impact officer at a UK Russell Group university with REF submission experience.
Write a complete REF 2029 impact case study using these exact sections:
### 1. Summary
(100-150 words. One paragraph. What is the impact? Who benefited?)
### 2. Underpinning Research
(200-300 words. Key findings, methodology, outputs.)
### 3. References to the Research
(5-10 formatted references with DOI if known.)
### 4. Details of the Impact
(700-800 words. Specific narrative: pathways, beneficiaries, reach, significance.)
### 5. Sources to Corroborate the Impact
(5-10 numbered sources.)
Ground every claim in evidence. Mark uncertain claims as [UNVERIFIED: reason].
Total target: 1800-2400 words."""

_AUDITOR_SYSTEM = """You are a strict REF impact case study auditor.
Output ONLY a valid JSON array of flags. Each element:
{"claim":"<20-word quote>","section":"<section title>","reason":"<why unverified>","severity":"warning|critical"}
If nothing unverified, output: []"""

async def _run_writer(title,authors,year,doi,citation_count,summary,evidence):
    author_str = ", ".join(authors[:6]) + (" et al." if len(authors)>6 else "")
    rich = [e for e in evidence if e.get("snippet")][:14]
    sparse = [e for e in evidence if not e.get("snippet")][:6]
    ev_lines = "\n".join(f"[{i+1}] ({e.get('kind','evidence').upper()}) {e.get('title','')} — {e.get('source','')}{': '+e['snippet'][:280] if e.get('snippet') else ''}" for i,e in enumerate(rich+sparse))
    user = f"Paper: {title}\nAuthors: {author_str or 'Unknown'}\nYear: {year or 'Unknown'}\nDOI: {doi or 'Not available'}\nCitations: {citation_count:,}\n\nPipeline summary:\n{summary[:700]}\n\nEvidence ({len(evidence)} items):\n{ev_lines or 'No evidence retrieved.'}\n\nWrite the complete REF 2029 impact case study now."
    result = await asyncio.to_thread(_call, _WRITER_SYSTEM, user, 8000)
    return result or ""

async def _run_auditor(case_study, evidence):
    ev_text = "\n".join(f"- {e.get('title','')}: {(e.get('snippet') or '')[:200]}" for e in evidence[:16] if e.get("title"))
    user = f"Case study to audit:\n{case_study[:3500]}\n\nEvidence:\n{ev_text or 'None.'}\n\nOutput the JSON flags array:"
    result = await asyncio.to_thread(_call, _AUDITOR_SYSTEM, user, 2000)
    if not result: return []
    m = re.search(r"\[.*?\]", result, re.DOTALL)
    if not m: return []
    try:
        flags = json.loads(m.group())
        return [f for f in flags if isinstance(f,dict) and "claim" in f and "severity" in f]
    except Exception:
        return []

def check_word_counts(case_study: str) -> dict[str,Any]:
    parts = re.split(r"###\s*\d+\.\s*", case_study)
    summary_wc=research_wc=impact_wc=0
    for part in parts:
        head = part.strip().lower(); wc = len(part.split())
        if head.startswith("summary"): summary_wc=wc
        elif head.startswith("underpinning research"): research_wc=wc
        elif head.startswith("details of"): impact_wc=wc
    total = len(case_study.split())
    return {"total":total,"summary":summary_wc,"research":research_wc,"impact":impact_wc,"total_ok":1800<=total<=2600,"summary_ok":80<=summary_wc<=180 if summary_wc else True,"research_ok":150<=research_wc<=380 if research_wc else True,"impact_ok":600<=impact_wc<=950 if impact_wc else True}

async def run_beta_ref(title,authors,year,doi,citation_count,summary,evidence):
    case_study = await _run_writer(title,authors,year,doi,citation_count,summary,evidence)
    if not case_study:
        return {"case_study":"","flags":[],"word_counts":check_word_counts(""),"error":"Writer agent returned no output. Check GOOGLE_API_KEY quota."}
    flags = await _run_auditor(case_study, evidence)
    return {"case_study":case_study,"flags":flags,"word_counts":check_word_counts(case_study)}
