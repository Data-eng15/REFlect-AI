"""Researcher profile builder — ORCID + OpenAlex (no scraping).

Given an ORCID iD (or a name + affiliation for manually-registered users), this
resolves the author on OpenAlex, pulls their highest-cited works, extracts their
research fields from OpenAlex "concepts", and asks the LLM to distil a short
profile narrative. The result powers the personalised dashboard (top papers,
greeting) and — later — field-aware dynamic retrieval (Phase 2).
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

import httpx

from .hf_synthesis import _call, _provider_label

OPENALEX_BASE = "https://api.openalex.org"
_MAILTO = os.getenv("OPENALEX_MAILTO", "dev@reflect.ai")
_HEADERS = {"User-Agent": f"REFlectAI/1.0 (mailto:{_MAILTO})"}
_WORK_SELECT = "title,publication_year,cited_by_count,doi,primary_location"


def _short_id(openalex_id: str) -> str:
    """'https://openalex.org/A5023888391' -> 'A5023888391'."""
    return (openalex_id or "").rstrip("/").split("/")[-1]


def _clean_orcid(orcid: str) -> str:
    """Accepts a bare iD or a full ORCID URL; returns the bare 16-digit iD."""
    m = re.search(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", orcid or "")
    return m.group(1) if m else (orcid or "")


def _affiliation(author: dict) -> Optional[str]:
    insts = author.get("last_known_institutions")
    if insts:
        return insts[0].get("display_name")
    inst = author.get("last_known_institution") or {}
    return inst.get("display_name")


def _fields_from_concepts(x_concepts: list[dict], max_fields: int = 6) -> list[str]:
    """Pick the researcher's salient fields. Prefer broad concepts (level 0/1)
    with a meaningful association score; fall back to whatever scores highest."""
    if not x_concepts:
        return []
    broad = [c for c in x_concepts if c.get("level", 0) <= 1 and c.get("score", 0) >= 10]
    chosen = broad or x_concepts
    seen: set[str] = set()
    out: list[str] = []
    for c in chosen:
        name = c.get("display_name")
        if name and name not in seen:
            seen.add(name)
            out.append(name)
        if len(out) >= max_fields:
            break
    return out


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> Optional[Any]:
    try:
        resp = await client.get(url, params=params, headers=_HEADERS, timeout=15)
        if resp.is_success:
            return resp.json()
    except Exception:
        pass
    return None


async def _author_by_orcid(client: httpx.AsyncClient, orcid: str) -> Optional[dict]:
    return await _get_json(client, f"{OPENALEX_BASE}/authors/https://orcid.org/{_clean_orcid(orcid)}")


async def _author_by_name(client: httpx.AsyncClient, name: str, affiliation: Optional[str]) -> Optional[dict]:
    data = await _get_json(client, f"{OPENALEX_BASE}/authors", {"search": name, "per_page": 5})
    results = (data or {}).get("results") or []
    if not results:
        return None
    if affiliation:
        aff = affiliation.lower()
        for a in results:
            inst = (_affiliation(a) or "").lower()
            if inst and (aff in inst or inst in aff):
                return a
    return results[0]


async def _top_works(client: httpx.AsyncClient, *, orcid: str | None = None,
                     author_id: str | None = None, n: int = 6) -> list[dict]:
    if orcid:
        filt = f"author.orcid:{_clean_orcid(orcid)}"
    elif author_id:
        filt = f"author.id:{_short_id(author_id)}"
    else:
        return []
    data = await _get_json(client, f"{OPENALEX_BASE}/works", {
        "filter": filt, "sort": "cited_by_count:desc", "per_page": n, "select": _WORK_SELECT,
    })
    works = (data or {}).get("results") or []
    out: list[dict] = []
    for w in works:
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        out.append({
            "title": w.get("title") or "Untitled",
            "year": w.get("publication_year"),
            "citations": w.get("cited_by_count", 0),
            "venue": src.get("display_name"),
            "doi": doi,
        })
    return out


def _split_name(display_name: str) -> tuple[str, str]:
    parts = (display_name or "").strip().split()
    if not parts:
        return "Researcher", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _profile_summary(profile: dict) -> tuple[str, str]:
    """LLM-distilled researcher profile narrative. Falls back to a deterministic
    sentence when no LLM provider is configured."""
    fields = ", ".join(profile["fields"][:4]) or "their discipline"
    papers = "; ".join(
        f"\"{p['title']}\" ({p['year']}, {p['citations']:,} citations)"
        for p in profile["top_papers"][:5]
    )
    system = (
        "You are a scholarly profiler. Write a concise, factual profile of a "
        "researcher for an academic impact tool. 55-75 words. No preamble, no "
        "bullet points, no hyperbole. Mention their dominant research areas, "
        "their most influential contribution, and recurring themes."
    )
    user = (
        f"Researcher: {profile['name']}\n"
        f"Affiliation: {profile['affiliation'] or 'unknown'}\n"
        f"Fields (OpenAlex concepts): {', '.join(profile['fields']) or 'unknown'}\n"
        f"Works: {profile['works_count']:,} · Total citations: {profile['total_citations']:,} · h-index: {profile['h_index']}\n"
        f"Most-cited works: {papers or 'none found'}\n\n"
        "Write the profile now."
    )
    text = _call(system, user, max_tokens=180)
    if text:
        return text.strip(), _provider_label()
    # Deterministic fallback
    top = profile["top_papers"][0]["title"] if profile["top_papers"] else "their work"
    return (
        f"{profile['name']} is a researcher in {fields} based at "
        f"{profile['affiliation'] or 'their institution'}, with {profile['works_count']:,} "
        f"publications and {profile['total_citations']:,} total citations "
        f"(h-index {profile['h_index']}). Their most influential contribution is \"{top}\"."
    ), "deterministic"


async def build_profile(*, orcid: Optional[str] = None, name: Optional[str] = None,
                        affiliation: Optional[str] = None) -> Optional[dict]:
    """Resolve a researcher via OpenAlex and assemble their profile.

    Returns None if the author cannot be resolved (caller should fall back to a
    demo/placeholder profile)."""
    async with httpx.AsyncClient() as client:
        author: Optional[dict] = None
        source = ""
        if orcid:
            author = await _author_by_orcid(client, orcid)
            source = "orcid"
        if author is None and name:
            author = await _author_by_name(client, name, affiliation)
            source = "name"
        if author is None:
            return None

        if orcid and source == "orcid":
            top = await _top_works(client, orcid=orcid)
        else:
            top = await _top_works(client, author_id=author.get("id"))

    stats = author.get("summary_stats") or {}
    display_name = author.get("display_name") or name or "Researcher"
    first, last = _split_name(display_name)
    profile: dict = {
        "source": source,
        "orcid": _clean_orcid(orcid) if orcid else (author.get("orcid") or "").split("/")[-1],
        "name": display_name,
        "first": first,
        "last": last,
        "affiliation": _affiliation(author) or affiliation,
        "fields": _fields_from_concepts(author.get("x_concepts") or []),
        "works_count": author.get("works_count", 0),
        "total_citations": author.get("cited_by_count", 0),
        "h_index": stats.get("h_index", 0),
        "i10_index": stats.get("i10_index", 0),
        "top_papers": top,
        "openalex_id": _short_id(author.get("id", "")),
    }
    summary, provider = _profile_summary(profile)
    profile["profile_summary"] = summary
    profile["summary_provider"] = provider
    return profile
