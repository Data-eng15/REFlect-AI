from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / ".data" / "impact_dataset.db"

def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with _conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT NOT NULL,
            agentic_faithfulness REAL, agentic_evidence_count INTEGER,
            agentic_sources TEXT, agentic_word_count INTEGER, agentic_rag_contexts INTEGER,
            baseline_faithfulness REAL, baseline_evidence_count INTEGER,
            baseline_word_count INTEGER, baseline_elapsed REAL,
            verdict TEXT, created_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_uid TEXT, doi TEXT,
            title TEXT NOT NULL, authors TEXT, year INTEGER,
            citation_count INTEGER DEFAULT 0, topics TEXT,
            faithfulness_score REAL, guardrail_status TEXT, model_provider TEXT,
            summary TEXT, evidence_count INTEGER DEFAULT 0, evidence_kinds TEXT,
            ref_report TEXT, query TEXT, created_at TEXT NOT NULL)""")
        cols = [r[1] for r in conn.execute("PRAGMA table_info(analyses)").fetchall()]
        if "user_uid" not in cols:
            conn.execute("ALTER TABLE analyses ADD COLUMN user_uid TEXT")

def save_analysis(state: dict, user_uid: str | None = None) -> None:
    meta = state.get("metadata")
    evidence = state.get("evidence", [])
    kinds = list({e.kind for e in evidence}) if evidence and hasattr(evidence[0], 'kind') else []
    with _conn() as conn:
        conn.execute("""INSERT INTO analyses
            (user_uid,doi,title,authors,year,citation_count,topics,
             faithfulness_score,guardrail_status,model_provider,
             summary,evidence_count,evidence_kinds,ref_report,query,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_uid,
             meta.doi if meta else None,
             meta.title if meta else state.get("query","Unknown"),
             json.dumps(meta.authors if meta else []),
             meta.year if meta else None,
             state.get("citation_count",0),
             json.dumps(state.get("topics",[])),
             state.get("faithfulness_score", state.get("faithfulness")),
             state.get("guardrail_status"),
             state.get("model_provider"),
             state.get("summary"),
             len(evidence),
             json.dumps(kinds),
             state.get("ref_report"),
             state.get("query"),
             datetime.now(timezone.utc).isoformat()))

def get_user_history(user_uid: str, limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("""SELECT query,title,doi,year,citation_count,faithfulness_score,created_at
            FROM analyses WHERE user_uid=? ORDER BY created_at DESC LIMIT ?""",
            (user_uid, limit)).fetchall()
        return [dict(r) for r in rows]

def get_dataset_rows() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM analyses ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

def save_evaluation(comparison: dict) -> None:
    ag = comparison.get("agentic", {})
    bl = comparison.get("baseline", {})
    with _conn() as conn:
        conn.execute("""INSERT INTO evaluations
            (query,agentic_faithfulness,agentic_evidence_count,agentic_sources,
             agentic_word_count,agentic_rag_contexts,baseline_faithfulness,
             baseline_evidence_count,baseline_word_count,baseline_elapsed,
             verdict,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (comparison.get("query"),
             ag.get("faithfulness_score"), ag.get("evidence_count"),
             json.dumps(ag.get("sources_used",[])), ag.get("word_count"),
             ag.get("rag_contexts"), bl.get("faithfulness_score"),
             bl.get("evidence_count"), bl.get("word_count"), bl.get("elapsed_seconds"),
             comparison.get("verdict"),
             datetime.now(timezone.utc).isoformat()))

def get_evaluations(limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM evaluations ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

def get_stats() -> dict:
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        avg_faith = conn.execute("SELECT AVG(faithfulness_score) FROM analyses WHERE faithfulness_score IS NOT NULL").fetchone()[0]
        avg_cit = conn.execute("SELECT AVG(citation_count) FROM analyses").fetchone()[0]
        return {"total_analyses": total, "avg_faithfulness": round(float(avg_faith or 0),2), "avg_citations": int(avg_cit or 0)}
