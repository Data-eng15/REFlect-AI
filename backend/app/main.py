from __future__ import annotations
import asyncio, csv, io, os, time, uuid
from collections import defaultdict
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .auth import create_linkedin_token, create_orcid_token, get_current_uid, get_current_user
from .profile import build_profile
from .domain_classifier import plan_routing
from .access_guard import DEMO_MODE, check_author_access
from .database import get_calibration_report, get_dataset_rows, get_evaluations, get_stats, get_user_history, init_db, save_analysis, save_calibration, save_evaluation
from .evaluation import run_comparison
from .models import AnalyzeRequest, AnalyzeResponse
from .ref_beta import run_beta_ref
from .services import analyze_paper, compose_summary
from .validation import classify_query, validate_query

app = FastAPI(title="REFlect AI API", version="0.5.0")

_rate_buckets: dict[str, list[float]] = defaultdict(list)

def _check_rate(key: str, limit: int, window: int) -> None:
    now = time.time()
    _rate_buckets[key] = [t for t in _rate_buckets[key] if now-t < window]
    if len(_rate_buckets[key]) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    _rate_buckets[key].append(now)

def rate_limit(request: Request, limit: int = 20, window: int = 60) -> None:
    ip = request.client.host if request.client else "unknown"
    _check_rate(ip, limit, window)

async def require_user(current_user: Optional[dict] = Depends(get_current_user)) -> dict:
    """Auth gate for expensive/LLM endpoints — 401 unless a valid ORCID/OAuth token
    is presented. Public read endpoints (search, stats, profile) remain open."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in with ORCID.")
    return current_user

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5175")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# Cloudflare Pages production + preview subdomains (e.g. https://reflect-ai.pages.dev,
# https://<hash>.reflect-ai.pages.dev). Regex avoids listing every ephemeral preview URL.
# Override with ALLOWED_ORIGIN_REGEX to add/replace a custom Pages domain.
_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX", r"https://([a-z0-9-]+\.)*pages\.dev")

app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_origin_regex=_origin_regex, allow_credentials=True, allow_methods=["GET","POST"], allow_headers=["Authorization","Content-Type","ngrok-skip-browser-warning"], max_age=600)

LINKEDIN_CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID","")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET","")
LINKEDIN_TOKEN_URL     = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL  = "https://api.linkedin.com/v2/userinfo"

# ORCID OAuth. Base defaults to production; set ORCID_OAUTH_BASE=https://sandbox.orcid.org for testing.
ORCID_CLIENT_ID     = os.getenv("ORCID_CLIENT_ID","")
ORCID_CLIENT_SECRET = os.getenv("ORCID_CLIENT_SECRET","")
ORCID_OAUTH_BASE    = os.getenv("ORCID_OAUTH_BASE","https://orcid.org").rstrip("/")
ORCID_CONFIGURED    = bool(ORCID_CLIENT_ID and ORCID_CLIENT_SECRET)

@app.on_event("startup")
async def startup() -> None:
    init_db()

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

def _crossref_candidate(work: dict) -> dict:
    title = (work.get("title") or ["Unknown title"])[0]
    venue = (work.get("container-title") or [""])[0]
    authors = [f"{a.get('given','')} {a.get('family','')}".strip() for a in work.get("author",[])[:5] if a.get("family")]
    year = None
    if "published-print" in work: year = work["published-print"].get("date-parts",[[None]])[0][0]
    elif "published-online" in work: year = work["published-online"].get("date-parts",[[None]])[0][0]
    return {"doi":work.get("DOI"),"title":title,"authors":authors,"year":year,"venue":venue,
            "type":work.get("type",""),"url":work.get("URL"),
            "citation_count":work.get("is-referenced-by-count",0) or 0}


def _norm_title(t: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


# Predatory / junk republication DOI prefixes. These registrants mass-republish
# existing papers under new DOIs with inflated metadata, polluting title search.
_JUNK_DOI_PREFIXES = ("10.65215/",)

def _is_junk_doi(doi: str | None) -> bool:
    if not doi:
        return False
    d = doi.lower().replace("https://doi.org/", "")
    return any(d.startswith(p) for p in _JUNK_DOI_PREFIXES)


async def _candidates_semantic_scholar(client: httpx.AsyncClient, q: str) -> list[dict]:
    """Semantic Scholar candidates — the only reliable source for canonical
    high-impact papers (e.g. the original 2017 'Attention Is All You Need').
    Uses the relevance /paper/search endpoint (returns citation counts directly,
    and consistently ranks the field-defining paper first), retried on 429. The
    /paper/autocomplete endpoint was found to 429 even with an API key, so it is
    no longer used."""
    import asyncio as _aio
    out: list[dict] = []
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    headers = {"x-api-key": key} if key else {}
    _ATTEMPTS = 3

    async def _get_with_retry(url, **kw):
        for attempt in range(_ATTEMPTS):
            try:
                r = await client.get(url, headers=headers, timeout=12, **kw)
                if r.status_code == 429 and attempt < _ATTEMPTS - 1:
                    await _aio.sleep(1.5 * (attempt + 1))
                    continue
                return r
            except Exception:
                if attempt < _ATTEMPTS - 1:
                    await _aio.sleep(1.0 * (attempt + 1))
                    continue
                return None
        return None

    r = await _get_with_retry(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={"query": q, "limit": 10,
                "fields": "title,year,authors,externalIds,citationCount,venue"})
    if not r or not r.is_success:
        return out
    for p in (r.json().get("data") or []):
        if not p:
            continue
        ext = p.get("externalIds") or {}
        doi = ext.get("DOI") or (f"10.48550/arXiv.{ext['ArXiv']}" if ext.get("ArXiv") else None)
        if _is_junk_doi(doi):
            continue
        out.append({
            "doi": doi,
            "title": p.get("title", "Unknown"),
            "authors": [a.get("name", "") for a in (p.get("authors") or [])[:5]],
            "year": p.get("year"),
            "venue": p.get("venue", "") or "",
            "type": "paper",
            "url": f"https://doi.org/{doi}" if doi else None,
            "citation_count": p.get("citationCount") or 0,
        })
    return out


async def _candidates_openalex(client: httpx.AsyncClient, q: str) -> list[dict]:
    """OpenAlex title search ranked by citation count."""
    out: list[dict] = []
    try:
        r = await client.get("https://api.openalex.org/works",
                             params={"filter": f"title.search:{q}",
                                     "sort": "cited_by_count:desc", "per-page": 6,
                                     "select": "title,doi,publication_year,cited_by_count,authorships,primary_location"},
                             timeout=12)
        if not r.is_success:
            return out
        for w in r.json().get("results", [])[:8]:
            doi_raw = (w.get("doi") or "")
            doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None
            if _is_junk_doi(doi):
                continue
            loc = (w.get("primary_location") or {}).get("source") or {}
            out.append({
                "doi": doi,
                "title": w.get("title", "Unknown"),
                "authors": [a.get("author", {}).get("display_name", "")
                            for a in (w.get("authorships") or [])[:5]],
                "year": w.get("publication_year"),
                "venue": loc.get("display_name", "") or "",
                "type": "paper",
                "url": f"https://doi.org/{doi}" if doi else None,
                "citation_count": w.get("cited_by_count") or 0,
            })
    except Exception:
        pass
    return out


_search_cache: dict[str, tuple[float, dict]] = {}
_SEARCH_TTL = 21600  # 6h — once a canonical paper is resolved, never regress

@app.get("/api/search")
async def search(request: Request, q: str = "") -> dict:
    rate_limit(request, limit=20, window=60)
    try: safe_q = validate_query(q)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc))
    kind = classify_query(safe_q)
    from urllib.parse import quote
    import asyncio as _aio

    # Serve a recent cached result so retries stay stable and SS load is reduced.
    cache_key = f"{kind}:{safe_q.lower().strip()}"
    cached = _search_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _SEARCH_TTL:
        return cached[1]

    async with httpx.AsyncClient() as client:
        # Direct DOI/arXiv lookup — single authoritative result
        if kind in ("doi", "arxiv"):
            try:
                r = await client.get(f"https://api.crossref.org/works/{quote(safe_q,safe='')}", timeout=12)
                if r.is_success:
                    return {"query": safe_q, "kind": kind,
                            "candidates": [{**_crossref_candidate(r.json()["message"]), "is_top_impact": True}]}
            except Exception:
                pass
            return {"query": safe_q, "kind": kind, "candidates": []}

        # Title query — gather candidates from THREE sources concurrently,
        # each carrying real citation counts so we can surface the
        # industry-defining paper rather than recent republications.
        ss, oa, cr = await _aio.gather(
            _candidates_semantic_scholar(client, safe_q),
            _candidates_openalex(client, safe_q),
            _crossref_title(client, safe_q),
        )

    # Merge + dedupe by normalised title. For each title group keep the
    # canonical version: highest citation count, tie-broken by EARLIEST year
    # (the original 2017 paper beats a 2025 republication of the same title).
    merged: dict[str, dict] = {}
    for c in (ss + oa + cr):
        if not c.get("title") or _is_junk_doi(c.get("doi")):
            continue
        key = _norm_title(c["title"])
        existing = merged.get(key)
        if existing is None:
            merged[key] = c
            continue
        c_cites = c.get("citation_count") or 0
        e_cites = existing.get("citation_count") or 0
        if c_cites > e_cites:
            merged[key] = c
        elif c_cites == e_cites and (c.get("year") or 9999) < (existing.get("year") or 9999):
            merged[key] = c

    candidates = list(merged.values())
    # Primary sort: citation count DESC (revolutionary paper first).
    # Tie-break: older year first (the original precedes republications).
    candidates.sort(key=lambda c: (-(c.get("citation_count") or 0), c.get("year") or 9999))
    candidates = candidates[:6]

    # Semantic Scholar is the ONLY source that reliably surfaces canonical,
    # field-defining papers (OpenAlex/CrossRef title search miss e.g. the 2017
    # "Attention Is All You Need"). So only claim a confident "highest impact"
    # when SS actually contributed; otherwise flag the result as low-confidence
    # and let the UI warn rather than badge a possibly-wrong paper.
    ss_ok = bool(ss)
    if candidates and ss_ok:
        candidates[0]["is_top_impact"] = True

    result = {"query": safe_q, "kind": kind, "candidates": candidates, "low_confidence": not ss_ok}
    # Cache only confident results; if SS failed, skip caching so we retry it.
    if ss_ok and candidates:
        _search_cache[cache_key] = (time.time(), result)
    return result


async def _crossref_title(client: httpx.AsyncClient, q: str) -> list[dict]:
    try:
        r = await client.get("https://api.crossref.org/works",
                             params={"query.title": q, "rows": 5}, timeout=12)
        if r.is_success:
            return [_crossref_candidate(w) for w in r.json().get("message", {}).get("items", [])]
    except Exception:
        pass
    return []

# Server-side draft store for the human-in-the-loop curation step. Holds the
# gathered evidence + candidate sentences between /api/analyze and /api/compose.
_draft_store: dict[str, tuple[float, dict]] = {}
_DRAFT_TTL = 1800  # 30 min

def _prune_drafts() -> None:
    now = time.time()
    for k in [k for k, (t, _) in _draft_store.items() if now - t > _DRAFT_TTL]:
        _draft_store.pop(k, None)

@app.post("/api/analyze")
async def analyze(request: Request, body: AnalyzeRequest = Body(...), current_user: dict = Depends(require_user)) -> dict:
    """Stage 1: gather evidence and draft one candidate sentence per evidence
    item for human curation. Does NOT produce the final summary — that happens
    in /api/compose once the reviewer selects sentences."""
    rate_limit(request, limit=10, window=60)
    try: safe_query = validate_query(body.query)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc))
    result = await analyze_paper(safe_query, fields=body.fields)
    meta = result.get("metadata")
    access = await check_author_access(doi=meta.doi if meta else None, user_name=current_user.get("name") if current_user else None, paper_authors=meta.authors if meta else None)

    _prune_drafts()
    draft_id = uuid.uuid4().hex
    _draft_store[draft_id] = (time.time(), {**result, "uid": current_user["uid"] if current_user else None})

    return {
        "draft_id": draft_id,
        "stage": "draft",
        "metadata": meta,
        "evidence": result["evidence"],
        "candidates": result["candidates"],
        "agent_statuses": result["agent_statuses"],
        "logs": result["logs"],
        "citation_count": result["citation_count"],
        "topics": result["topics"],
        "rag_context_count": result["rag_context_count"],
        "routing": result.get("routing", {}),
        "access": access,
    }

class ComposeRequest(BaseModel):
    draft_id: str
    selected_ids: list[int] = Field(default_factory=list)

@app.post("/api/compose")
async def compose(request: Request, body: ComposeRequest = Body(...), current_user: dict = Depends(require_user)) -> dict:
    """Stage 2: weave the reviewer-approved candidate sentences into the final
    REF summary, validate it, and return the full result."""
    rate_limit(request, limit=10, window=60)
    entry = _draft_store.get(body.draft_id)
    if not entry or (time.time() - entry[0]) > _DRAFT_TTL:
        raise HTTPException(status_code=404, detail="Draft expired — please re-run the analysis.")
    st = entry[1]
    evidence = st["evidence"]
    sel = set(body.selected_ids)
    selected = [c for c in st["candidates"] if c["id"] in sel]
    if not selected:
        raise HTTPException(status_code=422, detail="Select at least one sentence to compose a summary.")
    selected_evidence = [evidence[c["id"]] for c in selected if c["id"] < len(evidence)]
    sentences = [c["text"] for c in selected]

    comp = await asyncio.to_thread(
        compose_summary, st["metadata"], st["citation_count"], st["topics"],
        selected_evidence, sentences, st.get("rag_contexts", []),
    )
    full = {
        "metadata": st["metadata"],
        "summary": comp["summary"],
        "sections": comp["sections"],
        "evidence": evidence[:32],
        "agent_statuses": st["agent_statuses"],
        "logs": st["logs"] + comp["logs"],
        "faithfulness_score": comp["faithfulness_score"],
        "citation_count": comp["citation_count"],
        "topics": comp["topics"],
        "model_provider": comp["model_provider"],
        "rag_context_count": st["rag_context_count"],
        "guardrail_status": comp["guardrail_status"],
        "limitations": comp["limitations"],
        "ref_report": comp["ref_report"],
        "validation_report": comp["validation_report"],
    }
    save_analysis(full, user_uid=st.get("uid"))
    response = AnalyzeResponse(**full).model_dump()
    response["access"] = await check_author_access(doi=st["metadata"].doi if st["metadata"] else None, user_name=current_user.get("name") if current_user else None, paper_authors=st["metadata"].authors if st["metadata"] else None)
    response["routing"] = st.get("routing", {})
    response["references"] = comp["references"]
    return response

@app.get("/api/stats")
async def stats() -> dict:
    return get_stats()

@app.get("/api/dataset")
async def dataset(fmt: str = "json"):
    rows = get_dataset_rows()
    if fmt == "csv":
        if not rows: return StreamingResponse(io.StringIO(""), media_type="text/csv")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows); output.seek(0)
        return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition":"attachment; filename=reflect_ai_dataset.csv"})
    return {"count":len(rows),"rows":rows}

@app.get("/api/history")
async def history(request: Request, limit: int = 20, uid: Optional[str] = Depends(get_current_uid)) -> dict:
    if not uid: raise HTTPException(status_code=401, detail="Authentication required")
    rows = get_user_history(uid, limit=min(limit,50))
    return {"uid":uid,"queries":[r["query"] for r in rows if r.get("query")],"history":rows}

@app.post("/api/evaluate")
async def evaluate(request: Request, body: AnalyzeRequest = Body(...), current_user: dict = Depends(require_user)) -> dict:
    rate_limit(request, limit=5, window=60)
    try: safe_query = validate_query(body.query)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc))
    uid = current_user["uid"] if current_user else None
    agentic_result = await analyze_paper(safe_query)
    save_analysis(agentic_result, user_uid=uid)
    comparison = await run_comparison(safe_query, agentic_result)
    save_evaluation(comparison)
    comparison["agentic_full"] = AnalyzeResponse(**agentic_result).model_dump()
    return comparison

@app.get("/api/evaluate/history")
async def evaluate_history(limit: int = 20) -> dict:
    rows = get_evaluations(limit=min(limit,50))
    return {"count":len(rows),"rows":rows}

# ── Human-in-the-loop calibration ────────────────────────────────────────────

class CalibrationRequest(BaseModel):
    query: str
    title: Optional[str] = None
    reviewer: Optional[str] = None
    ai_faithfulness: Optional[float] = None
    human_faithfulness: Optional[float] = None
    ai_accuracy: Optional[float] = None
    human_accuracy: Optional[float] = None
    ai_completeness: Optional[float] = None
    human_completeness: Optional[float] = None
    ai_conciseness: Optional[float] = None
    human_conciseness: Optional[float] = None
    ai_overall: Optional[float] = None
    human_overall: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("query")
    @classmethod
    def _q_len(cls, v: str) -> str:
        if not v or len(v) > 500:
            raise ValueError("Invalid query")
        return v

@app.post("/api/calibrate")
async def calibrate(request: Request, body: CalibrationRequest = Body(...)) -> dict:
    """Submit a paired AI-vs-human rating for a generated summary.
    Builds the ground-truth dataset that quantifies how closely the AI judge
    tracks trained human reviewers."""
    rate_limit(request, limit=20, window=60)
    row_id = save_calibration(body.model_dump())
    report = get_calibration_report()
    return {"saved_id": row_id, "report": report}

@app.get("/api/calibration/report")
async def calibration_report() -> dict:
    """AI-vs-human agreement statistics: Pearson r, Spearman rho, and MAE
    per scoring dimension across all collected calibration samples."""
    return get_calibration_report()

class BetaRefRequest(BaseModel):
    query: str; title: str; authors: list[str] = []; year: Optional[int] = None
    doi: Optional[str] = None; citation_count: int = 0; summary: str = ""; evidence: list[dict] = []

@app.post("/api/ref/beta")
async def ref_beta(request: Request, body: BetaRefRequest = Body(...), current_user: dict = Depends(require_user)) -> dict:
    rate_limit(request, limit=5, window=60)
    try: validate_query(body.query)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc))
    access = await check_author_access(doi=body.doi, user_name=current_user.get("name") if current_user else None, paper_authors=body.authors or None)
    if not access["allowed"]:
        raise HTTPException(status_code=403, detail={"error":"author_verification_failed","message":access["reason"],"paper_authors":access["paper_authors"],"demo_mode":DEMO_MODE})
    result = await run_beta_ref(title=body.title, authors=body.authors, year=body.year, doi=body.doi, citation_count=body.citation_count, summary=body.summary, evidence=body.evidence)
    result["access"] = access
    return result

class LinkedInExchangeRequest(BaseModel):
    code: str; redirect_uri: str
    @field_validator("code")
    @classmethod
    def code_must_be_short(cls, v: str) -> str:
        if len(v) > 512: raise ValueError("Invalid authorization code")
        return v

@app.post("/api/auth/linkedin/exchange")
async def linkedin_exchange(request: Request, body: LinkedInExchangeRequest = Body(...)) -> dict:
    rate_limit(request, limit=5, window=60)
    if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="LinkedIn OAuth not configured.")
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(LINKEDIN_TOKEN_URL, data={"grant_type":"authorization_code","code":body.code,"redirect_uri":body.redirect_uri,"client_id":LINKEDIN_CLIENT_ID,"client_secret":LINKEDIN_CLIENT_SECRET}, headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=15)
        if not token_resp.is_success: raise HTTPException(status_code=400, detail="LinkedIn token exchange failed")
        access_token = token_resp.json().get("access_token","")
        profile_resp = await client.get(LINKEDIN_USERINFO_URL, headers={"Authorization":f"Bearer {access_token}"}, timeout=10)
        if not profile_resp.is_success: raise HTTPException(status_code=400, detail="Failed to fetch LinkedIn profile")
        profile = profile_resp.json()
        uid = f"linkedin:{profile.get('sub',profile.get('id','unknown'))}"
        email = profile.get("email",""); name = profile.get("name",profile.get("given_name","LinkedIn User"))
    jwt_token = create_linkedin_token(uid=uid, email=email, name=name)
    return {"token":jwt_token,"uid":uid,"email":email,"name":name}

class OrcidExchangeRequest(BaseModel):
    code: str; redirect_uri: str
    @field_validator("code")
    @classmethod
    def code_must_be_short(cls, v: str) -> str:
        if len(v) > 512: raise ValueError("Invalid authorization code")
        return v

@app.get("/api/auth/orcid/config")
async def orcid_config() -> dict:
    """Lets the frontend know whether to run real ORCID OAuth or the mock flow."""
    return {"configured": ORCID_CONFIGURED, "client_id": ORCID_CLIENT_ID, "authorize_base": ORCID_OAUTH_BASE}

@app.post("/api/auth/orcid/exchange")
async def orcid_exchange(request: Request, body: OrcidExchangeRequest = Body(...)) -> dict:
    rate_limit(request, limit=5, window=60)
    # Mock fallback — no credentials configured. Lets the showcase run end-to-end
    # without a registered ORCID client; flip on real OAuth by setting ORCID_CLIENT_ID/SECRET.
    if not ORCID_CONFIGURED:
        # Mock identity points at a real, resolvable ORCID so the personalised
        # dashboard populates from live OpenAlex data. Override with DEMO_ORCID.
        orcid = os.getenv("DEMO_ORCID", "0000-0002-9322-3515")
        uid = f"orcid:{orcid}"; name = "Demo Researcher"; email = ""
        jwt_token = create_orcid_token(uid=uid, email=email, name=name, orcid=orcid)
        return {"token":jwt_token,"uid":uid,"email":email,"name":name,"orcid":orcid,"mock":True}
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(f"{ORCID_OAUTH_BASE}/oauth/token", data={"grant_type":"authorization_code","code":body.code,"redirect_uri":body.redirect_uri,"client_id":ORCID_CLIENT_ID,"client_secret":ORCID_CLIENT_SECRET}, headers={"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"}, timeout=15)
        if not token_resp.is_success: raise HTTPException(status_code=400, detail="ORCID token exchange failed")
        data = token_resp.json()
        orcid = data.get("orcid",""); name = data.get("name") or "ORCID Researcher"
        uid = f"orcid:{orcid or 'unknown'}"; email = ""
    jwt_token = create_orcid_token(uid=uid, email=email, name=name, orcid=orcid)
    return {"token":jwt_token,"uid":uid,"email":email,"name":name,"orcid":orcid}

@app.get("/api/profile")
async def researcher_profile(
    request: Request,
    orcid: Optional[str] = None,
    name: Optional[str] = None,
    affiliation: Optional[str] = None,
) -> dict:
    """Build a personalised researcher profile (top papers, fields, LLM summary)
    from ORCID + OpenAlex. ?orcid=.. for ORCID users, or ?name=..&affiliation=..
    for manually-registered users. Returns {resolved: false} if not found."""
    rate_limit(request, limit=20, window=60)
    if not orcid and not name:
        raise HTTPException(status_code=422, detail="Provide an orcid or a name.")
    profile = await build_profile(orcid=orcid, name=name, affiliation=affiliation)
    if profile is None:
        return {"resolved": False}
    return {"resolved": True, "profile": profile}

@app.get("/api/routing/plan")
async def routing_plan(request: Request, fields: str = "", title: str = "") -> dict:
    """Preview the dynamic source-routing decision for a researcher (and,
    optionally, a specific paper). `fields` is a comma-separated list of the
    researcher's OpenAlex fields; `title` optionally layers the paper's own
    classified domain on top. Returns which sources will be queried vs skipped."""
    rate_limit(request, limit=60, window=60)
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    return plan_routing(fields=field_list, title=title)
