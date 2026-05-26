"""
Gemini-backed synthesiser — drop-in replacement for the HF local model.
Keeps the same HFSynthesizer class interface so services.py needs no changes.
Uses google/gemini-2.5-flash via REST (no extra SDK needed, just httpx).
"""
from __future__ import annotations

import asyncio
import os
import re

import httpx

from .models import EvidenceItem, PaperMetadata, TraceLog
from .services_support import log

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _api_key() -> str:
    return os.getenv("GOOGLE_API_KEY", "")


def _model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _call(system: str, user: str, max_tokens: int = 500) -> str | None:
    """Synchronous Gemini call (services.py calls via asyncio.to_thread)."""
    key = _api_key()
    if not key:
        return None
    url = f"{_GEMINI_BASE}/{_model()}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
    }
    try:
        resp = httpx.post(url, params={"key": key}, json=payload, timeout=90)
        if not resp.is_success:
            try:
                err = resp.json().get("error", {}).get("message", resp.text[:120])
            except Exception:
                err = resp.text[:120]
            _last_error.append(f"Gemini {resp.status_code}: {err}")
            return None
        candidates = resp.json().get("candidates", [])
        if not candidates:
            return None
        return candidates[0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        _last_error.append(str(exc))
        return None


_last_error: list[str] = []


class HFSynthesizer:
    """Gemini-backed synthesiser with the same interface as the original HF class."""

    def enabled(self) -> bool:
        return bool(_api_key())

    def generate(
        self,
        metadata: PaperMetadata,
        citation_count: int,
        evidence: list[EvidenceItem],
        topics: list[str],
        rag_contexts: list[str],
    ) -> tuple[str | None, str, list[TraceLog]]:
        logs: list[TraceLog] = []
        if not self.enabled():
            logs.append(log("LLM", "GOOGLE_API_KEY not set — using deterministic synthesis. Add it to backend/.env."))
            return None, "deterministic", logs

        ev = "\n".join(
            f"- [{e.kind.upper()}] {e.title} ({e.source}, {e.year or 'n.d.'}) — {(e.snippet or '')[:200]}"
            for e in evidence[:12]
        )
        rag = "\n".join(f"• {c[:400]}" for c in rag_contexts[:5])

        system = (
            "You are a rigorous research impact analyst. Ground every claim in the evidence. "
            "Do not invent statistics or institutions. Acknowledge uncertainty when evidence is thin."
        )
        user = f"""Write a 200-word impact narrative for this paper based strictly on the evidence below.

Paper: {metadata.title}
Authors: {", ".join(metadata.authors[:5]) or "Unknown"}
Year: {metadata.year or "Unknown"}
Citations: {citation_count:,}
Topics: {", ".join(topics[:6]) or "Not identified"}

Evidence:
{ev or "No external evidence retrieved."}

RAG context:
{rag or "None."}

Write exactly one paragraph (~200 words). Be honest about uncertainty."""

        summary = _call(system, user, max_tokens=2000)
        if summary:
            logs.append(log("LLM", "Gemini generated impact narrative", model=_model(), words=len(summary.split())))
            return summary, f"gemini:{_model()}", logs

        err = _last_error[-1] if _last_error else "unknown error"
        logs.append(log("LLM", f"Gemini failed ({err[:80]}) — falling back to deterministic synthesis"))
        return None, "deterministic", logs

    def generate_ref_report(
        self,
        metadata: PaperMetadata,
        evidence: list[EvidenceItem],
        summary: str,
        topics: list[str],
    ) -> tuple[str | None, list[TraceLog]]:
        logs: list[TraceLog] = []
        if not self.enabled():
            return None, logs

        ev = "\n".join(
            f"- [{e.kind.upper()}] {e.title} ({e.source})"
            for e in evidence[:15]
        )
        system = (
            "You are an expert in UK Research Excellence Framework (REF) impact case studies. "
            "Write formal, evidence-grounded REF narratives. Use academic prose."
        )
        user = f"""Write a formal REF Impact Case Study with these exact markdown headings:

### 1. Summary of Impact
### 2. Underpinning Research
### 3. Details of Impact
### 4. References to the Research

Paper: {metadata.title}
Authors: {", ".join(metadata.authors) or "Unknown"}
Year: {metadata.year or "Unknown"}
DOI: {metadata.doi or "N/A"}
Topics: {", ".join(topics) or "N/A"}
Impact summary: {summary}

Evidence:
{ev or "Limited evidence available."}

Write ~400 words in formal REF style."""

        report = _call(system, user, max_tokens=4000)
        if report:
            logs.append(log("LLM", "Gemini generated REF case study", model=_model()))
            return report, logs
        return None, logs

    def evaluate_faithfulness(
        self,
        summary: str,
        evidence: list[EvidenceItem],
        rag_contexts: list[str],
    ) -> tuple[float, list[TraceLog]]:
        logs: list[TraceLog] = []
        if not self.enabled():
            return -1.0, logs

        ev = "\n".join(f"- {e.title}: {(e.snippet or '')[:150]}" for e in evidence[:10])
        prompt = f"""Rate faithfulness of this summary against the evidence (0–10, integer only).
0 = hallucinated, 10 = every claim supported. Output ONLY the integer.

Summary: {summary[:500]}

Evidence:
{ev}

Rating:"""

        result = _call("You are a strict academic faithfulness judge.", prompt, max_tokens=50)
        if result:
            m = re.search(r"\d+", result)
            if m:
                score = min(10, max(0, int(m.group(0)))) / 10.0
                logs.append(log("Judge", f"Gemini faithfulness score: {score}", model=_model()))
                return score, logs
        return -1.0, logs


hf_synthesizer = HFSynthesizer()
