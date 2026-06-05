"""
Multi-provider LLM synthesiser.

Priority order:
  1. Groq  (GROQ_API_KEY)  → llama-3.3-70b-versatile  — 30 req/min free tier
  2. Gemini (GOOGLE_API_KEY) → gemini-2.5-flash          — 20 req/min free tier

Keeps the same HFSynthesizer class interface so services.py needs no changes.
"""
from __future__ import annotations

import json as _json
import os
import re
import time

import httpx

from .models import EvidenceItem, PaperMetadata, TraceLog
from .services_support import log

# ── Provider endpoints ────────────────────────────────────────────────────────
_GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

_last_error: list[str] = []


# ── Key helpers ───────────────────────────────────────────────────────────────

def _groq_key() -> str:
    return os.getenv("GROQ_API_KEY", "")

def _gemini_key() -> str:
    return os.getenv("GOOGLE_API_KEY", "")

def _gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def _active_provider() -> str:
    """Return which provider is currently configured."""
    if _groq_key():
        return "groq"
    if _gemini_key():
        return "gemini"
    return "none"


# ── Groq call (OpenAI-compatible) ─────────────────────────────────────────────

def _call_groq(system: str, user: str, max_tokens: int = 500) -> str | None:
    key = _groq_key()
    if not key:
        return None
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    for attempt in range(2):
        try:
            resp = httpx.post(
                _GROQ_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429 and attempt == 0:
                # Groq returns Retry-After header in seconds
                wait = float(resp.headers.get("retry-after", 30)) + 2
                _last_error.append(f"Groq 429: rate-limited, retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            if not resp.is_success:
                try:
                    err = resp.json().get("error", {}).get("message", resp.text[:120])
                except Exception:
                    err = resp.text[:120]
                _last_error.append(f"Groq {resp.status_code}: {err}")
                return None
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            _last_error.append(f"Groq exception: {exc}")
            return None
    return None


# ── Gemini call ───────────────────────────────────────────────────────────────

def _call_gemini(system: str, user: str, max_tokens: int = 500) -> str | None:
    key = _gemini_key()
    if not key:
        return None
    model = _gemini_model()
    url = f"{_GEMINI_BASE}/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.3,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    for attempt in range(2):
        try:
            resp = httpx.post(url, params={"key": key}, json=payload, timeout=90)
            if resp.status_code in (429, 503) and attempt == 0:
                try:
                    err_msg = resp.json().get("error", {}).get("message", "")
                    m = re.search(r"retry in ([\d.]+)s", err_msg)
                    wait = min(float(m.group(1)) + 2, 65) if m else 60
                except Exception:
                    wait = 60
                _last_error.append(f"Gemini {resp.status_code}: rate-limited, retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
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
            parts = candidates[0]["content"].get("parts", [])
            text_parts = [p.get("text", "") for p in parts if not p.get("thought", False)]
            if not text_parts:
                return None
            return text_parts[-1].strip()
        except Exception as exc:
            _last_error.append(f"Gemini exception: {exc}")
            return None
    return None


# ── Unified call — tries Groq first, falls back to Gemini ────────────────────

def _call(system: str, user: str, max_tokens: int = 500) -> str | None:
    if _groq_key():
        result = _call_groq(system, user, max_tokens)
        if result:
            return result
        # Groq failed — try Gemini if available
        if _gemini_key():
            _last_error.append("Groq failed, falling back to Gemini")
            return _call_gemini(system, user, max_tokens)
        return None
    if _gemini_key():
        return _call_gemini(system, user, max_tokens)
    return None


def _provider_label() -> str:
    if _groq_key():
        return f"groq:{os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}"
    if _gemini_key():
        return f"gemini:{_gemini_model()}"
    return "deterministic"


# ── HFSynthesizer (same public interface, new multi-provider internals) ───────

class HFSynthesizer:
    """Multi-provider synthesiser: Groq → Gemini → deterministic fallback."""

    def enabled(self) -> bool:
        return bool(_groq_key() or _gemini_key())

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
            logs.append(log("LLM", "No LLM key set — using deterministic synthesis. Add GROQ_API_KEY or GOOGLE_API_KEY to backend/.env."))
            return None, "deterministic", logs

        ev = "\n".join(
            f"- [{e.kind.upper()}] {e.title} ({e.source}, {e.year or 'n.d.'}) — {(e.snippet or '')[:200]}"
            for e in evidence[:12]
        )

        system = (
            "You are a rigorous UK Research Excellence Framework (REF) impact analyst. "
            "Ground every claim in the provided evidence. Do not invent statistics, companies, or institutions. "
            "Acknowledge uncertainty only when evidence is genuinely thin. "
            "Write in the style of a REF impact case study: dense, evidence-grounded academic prose."
        )
        user = f"""Write a single REF-style impact paragraph. Target length: 120–130 words.

Paper: {metadata.title}
Authors: {", ".join(metadata.authors[:3]) or "Unknown"}
Year: {metadata.year or "Unknown"}
Citations: {citation_count:,}

Evidence:
{ev or "No evidence retrieved."}

CONTENT — five sentences, each 24–26 words:
  1. What the paper introduced and why it was a significant contribution to its field.
  2. Citation reach: state {citation_count:,} citations and name 2 specific citing works from the evidence above.
  3. Real-world adoption: name a specific patent AND a specific code repository from the evidence, with details.
  4. A second adoption pathway or an honest acknowledgement of what evidence is missing.
  5. Overall significance and lasting impact on the field.

FORMAT:
- ONE flowing paragraph. No headings, no lists, no bullet points.
- Use **bold** on exactly 3–4 key phrases.
- No invented facts — every claim must appear in the evidence above."""

        summary = _call(system, user, max_tokens=500)
        if summary:
            provider = _provider_label()
            logs.append(log("LLM", f"{provider.split(':')[0].title()} generated impact narrative", model=provider, words=len(summary.split())))
            return summary, provider, logs

        err = _last_error[-1] if _last_error else "unknown error"
        logs.append(log("LLM", f"LLM failed ({err[:80]}) — falling back to deterministic synthesis"))
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

        ev_all = "\n".join(
            f"- [{e.kind.upper()}] {e.title} ({e.source}, {e.year or 'n.d.'})"
            for e in evidence[:15]
        )
        system = (
            "You are a UK Research Excellence Framework (REF) impact analyst. "
            "Write concise, evidence-grounded academic prose. "
            "Use **bold** markdown for 3–4 key impact phrases only."
        )
        user = f"""Write a single REF-style impact paragraph. Target length: 120–130 words.

Paper: {metadata.title}
Authors: {", ".join(metadata.authors[:4]) or "Unknown"}
Year: {metadata.year or "Unknown"}
DOI: {metadata.doi or "N/A"}
Topics: {", ".join(topics[:4]) or "N/A"}
Overview: {summary}

Evidence:
{ev_all or "Limited evidence available."}

CONTENT — five sentences, each 24–26 words:
  1. Core contribution — what the paper introduced to the field, with context.
  2. Citation reach — state count and name 2 specific citing works from evidence.
  3. Real-world adoption — name specific patents and code repos from evidence with detail.
  4. Broader societal or disciplinary impact drawn from evidence.
  5. Overall REF significance — why this paper matters beyond academia.

FORMAT:
- ONE flowing paragraph, no headings, no lists.
- Use **bold** on 3–4 key impact phrases.
- No invented facts — ground every claim in the evidence above."""

        report = _call(system, user, max_tokens=500)
        if report:
            provider = _provider_label()
            logs.append(log("LLM", f"{provider.split(':')[0].title()} generated REF paragraph", model=provider))
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

        result = _call("You are a strict academic faithfulness judge.", prompt, max_tokens=10)
        if result:
            m = re.search(r"\d+", result)
            if m:
                score = min(10, max(0, int(m.group(0)))) / 10.0
                provider = _provider_label()
                logs.append(log("Judge", f"Faithfulness score: {score}", model=provider))
                return score, logs
        return -1.0, logs

    def cross_validate_summary(
        self,
        summary: str,
        evidence: list[EvidenceItem],
        citation_count: int,
        metadata: "PaperMetadata",
    ) -> tuple[dict, list[TraceLog]]:
        """Independent peer-reviewer pass. Returns scored validation report."""
        logs: list[TraceLog] = []
        if not self.enabled():
            return {}, logs

        ev = "\n".join(
            f"- [{e.kind.upper()}] {e.title} ({e.source}, {e.year or 'n.d.'}): {(e.snippet or '')[:200]}"
            for e in evidence[:12]
        )
        system = (
            "You are an independent academic peer-reviewer assessing AI-generated research impact summaries. "
            "Be critical, precise, and evidence-grounded. Never be generous without justification."
        )
        prompt = f"""Peer-review this 100-word AI-generated research impact summary.

=== PAPER ===
Title: {metadata.title}
Authors: {", ".join(metadata.authors[:5]) or "Unknown"}
Year: {metadata.year or "?"}
Real citation count: {citation_count:,}

=== SUMMARY TO REVIEW ===
{summary}

=== AVAILABLE EVIDENCE ===
{ev or "No evidence available."}

Score each dimension 1–10 and give a one-line reason:
1. Accuracy – are all claims supported by evidence?
2. Completeness – are key impacts covered?
3. Conciseness – is it tight and free of padding?
4. Word count adherence – is it ~100 words?

Then write 2–3 sentences of overall feedback.

Respond in this exact JSON format:
{{
  "accuracy": <1-10>,
  "accuracy_reason": "<one line>",
  "completeness": <1-10>,
  "completeness_reason": "<one line>",
  "conciseness": <1-10>,
  "conciseness_reason": "<one line>",
  "word_count_score": <1-10>,
  "word_count_reason": "<one line>",
  "overall_score": <1-10>,
  "feedback": "<2-3 sentence peer review>"
}}"""

        raw = _call(system, prompt, max_tokens=600)
        if raw:
            try:
                json_match = re.search(r"\{[\s\S]*\}", raw)
                if json_match:
                    report = _json.loads(json_match.group(0))
                    provider = _provider_label()
                    logs.append(log("CrossValidator", "Peer review complete",
                                    overall=report.get("overall_score"), model=provider))
                    return report, logs
            except Exception as exc:
                logs.append(log("CrossValidator", f"JSON parse failed: {exc}", raw=raw[:100]))
        return {}, logs


hf_synthesizer = HFSynthesizer()
