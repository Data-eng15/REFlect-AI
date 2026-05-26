from __future__ import annotations
import difflib, os, re
from typing import Any, Optional
import httpx

DEMO_MODE: bool = os.getenv("DEMO_MODE","true").lower() in ("true","1","yes")

def _normalise(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z\s]","",name)
    return " ".join(name.split())

def _name_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()

def _match_user_to_authors(user_name: str, authors: list[str]) -> tuple[bool, Optional[str], float]:
    best_score, best_author = 0.0, None
    for author in authors:
        score = _name_similarity(user_name, author)
        if score > best_score:
            best_score = score
            best_author = author
    matched = best_score >= 0.72
    return matched, (best_author if matched else None), round(best_score,3)

async def _fetch_crossref_authors(doi: str) -> list[str]:
    from urllib.parse import quote
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://api.crossref.org/works/{quote(doi,safe='')}", timeout=10)
            if not r.is_success: return []
            return [f"{a.get('given','')} {a.get('family','')}".strip() for a in r.json().get("message",{}).get("author",[]) if a.get("family")]
    except Exception:
        return []

async def check_author_access(doi: Optional[str], user_name: Optional[str], paper_authors: Optional[list[str]] = None) -> dict[str, Any]:
    if not doi:
        return _result(True, False, "No DOI — author verification skipped.", paper_authors or [], None, 0.0)
    authors = paper_authors or await _fetch_crossref_authors(doi)
    if not authors:
        return _result(True, False, "CrossRef returned no author metadata.", [], None, 0.0)
    if not user_name:
        return _result(DEMO_MODE, False, "Anonymous — sign in to unlock full document generation.", authors, None, 0.0)
    matched, matched_author, score = _match_user_to_authors(user_name, authors)
    if matched:
        return _result(True, True, f"Author identity confirmed: '{matched_author}' (score {score}).", authors, matched_author, score)
    reason = (f"'{user_name}' not listed as author (best match score {score}). " +
              ("DEMO MODE: access permitted for evaluation." if DEMO_MODE else "Access blocked."))
    return _result(DEMO_MODE, False, reason, authors, None, score)

def _result(allowed,verified,reason,paper_authors,matched_author,score):
    return {"allowed":allowed,"verified":verified,"demo_mode":DEMO_MODE,"matched_author":matched_author,"score":score,"paper_authors":paper_authors,"reason":reason}
