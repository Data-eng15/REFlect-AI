from __future__ import annotations
import csv, io, os, time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from .auth import create_linkedin_token, get_current_uid, get_current_user
from .access_guard import DEMO_MODE, check_author_access
from .database import get_dataset_rows, get_evaluations, get_stats, get_user_history, init_db, save_analysis, save_evaluation
from .evaluation import run_comparison
from .models import AnalyzeRequest, AnalyzeResponse
from .ref_beta import run_beta_ref
from .services import analyze_paper
from .validation import classify_query, validate_query

app = FastAPI(title="Veritrace API", version="0.5.0")

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

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5175")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["GET","POST"], allow_headers=["Authorization","Content-Type"], max_age=600)

LINKEDIN_CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID","")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET","")
LINKEDIN_TOKEN_URL     = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL  = "https://api.linkedin.com/v2/userinfo"

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
    return {"doi":work.get("DOI"),"title":title,"authors":authors,"year":year,"venue":venue,"type":work.get("type",""),"url":work.get("URL")}

@app.get("/api/search")
async def search(request: Request, q: str = "") -> dict:
    rate_limit(request, limit=20, window=60)
    try: safe_q = validate_query(q)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc))
    kind = classify_query(safe_q)
    candidates = []
    from urllib.parse import quote
    async with httpx.AsyncClient() as client:
        if kind in ("doi","arxiv"):
            try:
                r = await client.get(f"https://api.crossref.org/works/{quote(safe_q,safe='')}", timeout=12)
                if r.is_success: candidates = [_crossref_candidate(r.json()["message"])]
            except Exception: pass
        else:
            try:
                r = await client.get("https://api.crossref.org/works", params={"query.title":safe_q,"rows":5}, timeout=12)
                if r.is_success: candidates = [_crossref_candidate(w) for w in r.json().get("message",{}).get("items",[])]
            except Exception: pass
    return {"query":safe_q,"kind":kind,"candidates":candidates}

@app.post("/api/analyze")
async def analyze(request: Request, body: AnalyzeRequest = Body(...), current_user: Optional[dict] = Depends(get_current_user)) -> dict:
    rate_limit(request, limit=10, window=60)
    try: safe_query = validate_query(body.query)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc))
    uid = current_user["uid"] if current_user else None
    result = await analyze_paper(safe_query)
    save_analysis(result, user_uid=uid)
    meta = result.get("metadata")
    access = await check_author_access(doi=meta.doi if meta else None, user_name=current_user.get("name") if current_user else None, paper_authors=meta.authors if meta else None)
    response = AnalyzeResponse(**result).model_dump()
    response["access"] = access
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
        return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition":"attachment; filename=veritrace_dataset.csv"})
    return {"count":len(rows),"rows":rows}

@app.get("/api/history")
async def history(request: Request, limit: int = 20, uid: Optional[str] = Depends(get_current_uid)) -> dict:
    if not uid: raise HTTPException(status_code=401, detail="Authentication required")
    rows = get_user_history(uid, limit=min(limit,50))
    return {"uid":uid,"queries":[r["query"] for r in rows if r.get("query")],"history":rows}

@app.post("/api/evaluate")
async def evaluate(request: Request, body: AnalyzeRequest = Body(...), current_user: Optional[dict] = Depends(get_current_user)) -> dict:
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

class BetaRefRequest(BaseModel):
    query: str; title: str; authors: list[str] = []; year: Optional[int] = None
    doi: Optional[str] = None; citation_count: int = 0; summary: str = ""; evidence: list[dict] = []

@app.post("/api/ref/beta")
async def ref_beta(request: Request, body: BetaRefRequest = Body(...), current_user: Optional[dict] = Depends(get_current_user)) -> dict:
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
