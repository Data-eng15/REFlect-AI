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
        # Human-in-the-loop calibration: pairs AI scores with human reviewer ratings
        conn.execute("""CREATE TABLE IF NOT EXISTS calibrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL, title TEXT, reviewer TEXT,
            ai_faithfulness REAL, human_faithfulness REAL,
            ai_accuracy REAL, human_accuracy REAL,
            ai_completeness REAL, human_completeness REAL,
            ai_conciseness REAL, human_conciseness REAL,
            ai_overall REAL, human_overall REAL,
            notes TEXT, created_at TEXT NOT NULL)""")

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


# ── Human-in-the-loop calibration ────────────────────────────────────────────

def save_calibration(payload: dict) -> int:
    """Store a paired AI-vs-human rating. Returns the new row id."""
    with _conn() as conn:
        cur = conn.execute("""INSERT INTO calibrations
            (query,title,reviewer,
             ai_faithfulness,human_faithfulness,
             ai_accuracy,human_accuracy,
             ai_completeness,human_completeness,
             ai_conciseness,human_conciseness,
             ai_overall,human_overall,notes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (payload.get("query"), payload.get("title"), payload.get("reviewer"),
             payload.get("ai_faithfulness"), payload.get("human_faithfulness"),
             payload.get("ai_accuracy"), payload.get("human_accuracy"),
             payload.get("ai_completeness"), payload.get("human_completeness"),
             payload.get("ai_conciseness"), payload.get("human_conciseness"),
             payload.get("ai_overall"), payload.get("human_overall"),
             payload.get("notes"),
             datetime.now(timezone.utc).isoformat()))
        return cur.lastrowid


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    denom = (vx * vy) ** 0.5
    if denom == 0:
        return None
    return round(cov / denom, 3)


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    def _rank(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
            i = j + 1
        return ranks
    return _pearson(_rank(xs), _rank(ys))


def _mae(xs: list[float], ys: list[float]) -> float | None:
    if not xs:
        return None
    return round(sum(abs(x - y) for x, y in zip(xs, ys)) / len(xs), 3)


def get_calibration_report() -> dict:
    """Compute AI-vs-human agreement statistics across all calibration records."""
    with _conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM calibrations ORDER BY created_at DESC").fetchall()]

    n = len(rows)
    dims = {
        "faithfulness": ("ai_faithfulness", "human_faithfulness"),
        "accuracy":     ("ai_accuracy", "human_accuracy"),
        "completeness": ("ai_completeness", "human_completeness"),
        "conciseness":  ("ai_conciseness", "human_conciseness"),
        "overall":      ("ai_overall", "human_overall"),
    }
    report: dict = {"n_samples": n, "dimensions": {}, "records": rows[:50]}
    for dim, (ak, hk) in dims.items():
        pairs = [(r[ak], r[hk]) for r in rows
                 if r.get(ak) is not None and r.get(hk) is not None]
        if not pairs:
            report["dimensions"][dim] = {"n": 0, "pearson": None,
                                         "spearman": None, "mae": None,
                                         "ai_mean": None, "human_mean": None}
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        report["dimensions"][dim] = {
            "n": len(pairs),
            "pearson": _pearson(xs, ys),
            "spearman": _spearman(xs, ys),
            "mae": _mae(xs, ys),
            "ai_mean": round(sum(xs) / len(xs), 3),
            "human_mean": round(sum(ys) / len(ys), 3),
        }
    return report
