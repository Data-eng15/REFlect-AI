from __future__ import annotations
import re

MAX_QUERY_LEN = 4_000
_DOI_RE    = re.compile(r"^10\.\d{4,9}/[^\s]+$")
_ARXIV_RE  = re.compile(r"^(arxiv:)?\d{4}\.\d{4,5}(v\d+)?$", re.IGNORECASE)
_BIBTEX_RE = re.compile(r"^\s*@\w+\s*\{", re.DOTALL)
_BANNED = ("<script","javascript:","\x00","../","..\\","drop table","delete from","insert into","union select","--","exec(","system(","os.system","__import__")

def validate_query(raw: str) -> str:
    query = raw.strip()
    if not query: raise ValueError("Query cannot be empty.")
    if len(query) > MAX_QUERY_LEN: raise ValueError(f"Query too long ({len(query):,} chars). Max {MAX_QUERY_LEN:,}.")
    ql = query.lower()
    for p in _BANNED:
        if p in ql: raise ValueError("Query contains disallowed content.")
    return query

def classify_query(query: str) -> str:
    q = query.strip()
    if _DOI_RE.match(q): return "doi"
    if _ARXIV_RE.match(q): return "arxiv"
    if _BIBTEX_RE.match(q): return "bibtex"
    return "title"
