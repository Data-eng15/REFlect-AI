# REFlect AI — Personalised Research Impact Assessment

> Sign in with your ORCID iD, and REFlect AI conditions the whole analysis on *you*: it profiles the researcher, traces a paper's **downstream influence** — citations, code, patents, policy, funding — through open research data, drafts one evidence-grounded sentence per source for **you to curate**, and composes an auditable, reference-cited REF-aligned impact narrative.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-blue?logo=react)](https://react.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2-orange)](https://github.com/langchain-ai/langgraph)
[![LLM](https://img.shields.io/badge/LLM-Groq%20Llama%203.3%2070B%20%2B%20Gemini-blue)](https://groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Screenshots

### Landing Page
![Landing Page](docs/screenshots/01_landing_page.png)

### Sign In (ORCID iD)
![Login Modal](docs/screenshots/03_login_modal.png)

### Personalised Researcher Dashboard
![Dashboard](docs/screenshots/04_dashboard_empty.png)

### Capabilities
![Capabilities](docs/screenshots/02_capabilities.png)

---

## What It Does

REFlect AI is a **personalised, field-aware multi-agent pipeline** that conditions impact analysis on the individual researcher and keeps a human accountable for every claim:

| Step | What happens |
|---|---|
| **1. Profile** | On ORCID sign-in, builds a researcher profile (highest-cited works, research fields, bibliometrics) from open scholarly data |
| **2. Resolve** | Accepts DOI, arXiv ID, or paper title — resolves to canonical metadata across complementary scholarly indices |
| **3. Route** | A field-aware classifier selects which evidence sources to query, with core sources always on and a recall-preserving fallback |
| **4. Retrieve** | Parallel agents fetch evidence — citations, code, patents, policy, funding, and biomedical/clinical sources |
| **5. Trace** | Downstream-impact tracer follows the citing literature, elevating works that out-cite the source or attract their own funding |
| **6. Draft → Curate → Compose** | Drafts one grounded sentence per source; **you select which to keep**; composes the final narrative from approved sentences only |
| **7. Validate** | Independent faithfulness judge (0–1) and a four-dimension peer-reviewer score the output |
| **8. Audit** | Every agent step, routing decision, API call, and evidence source is logged and shown in the UI |

---

## Features

- **ORCID-personalised analysis** — profile-driven retrieval and framing conditioned on the researcher under assessment
- **Dynamic field-aware routing** — a visible panel shows which sources were queried vs skipped, and why
- **Downstream-impact tracing** — evidences impact through what a paper *enabled*, not raw citation count
- **Human-in-the-loop curation** — subtractive sentence selection so a human vouches for every claim before it enters the narrative
- **Reference-grounded synthesis** — inline `[n]` citations with a numbered reference list; every claim traces to a source
- **Dual-model validation** — faithfulness judge + independent peer-reviewer on every summary
- **Beta REF 2029 writer** — generates a full UK Research Excellence Framework impact case study with an auditor agent that flags unverified claims
- **Glass-box auditability** — full agent log, every source URL, faithfulness score on every summary
- **Multi-auth** — Sign in with ORCID iD, institutional / LinkedIn sign-in, or Demo Access (no account needed)
- **Export** — download all analyses as a CSV dataset

---

## Data Sources

| Source | What it provides |
|---|---|
| CrossRef | Paper metadata, abstract, authors, DOI resolution |
| OpenAlex | Researcher profile, citation counts, topic labels, downstream citing works |
| Semantic Scholar | Paper resolution and citation graph |
| GitHub | Code repositories implementing the paper |
| Google Patents | Patent cross-references |
| Europe PMC | Biomedical literature and policy mentions |
| UKRI Gateway | UK research grant funding signals |

---

## Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — async REST API
- [LangGraph](https://github.com/langchain-ai/langgraph) — multi-agent state machine orchestration
- [ChromaDB](https://www.trychroma.com/) — local vector store for RAG
- [sentence-transformers](https://sbert.net/) — `all-MiniLM-L6-v2` embeddings (runs on CPU)
- **Groq Llama 3.3 70B** (primary) + **Gemini 2.5 Flash** (automatic fallback) — synthesis + faithfulness scoring, behind one provider-agnostic interface
- [SQLite](https://www.sqlite.org/) — persistent analysis & evaluation history
- [PyJWT](https://pyjwt.readthedocs.io/) — ORCID / LinkedIn OAuth token signing

**Frontend**
- [React 18](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- [Vite](https://vitejs.dev/) — fast dev server + build
- [React Router v7](https://reactrouter.com/) — SPA routing
- [Lucide React](https://lucide.dev/) — icon library
- **REFlect AI Design System** — Source Serif 4 · Inter · JetBrains Mono · white academic aesthetic

---

## Run Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- A free [Groq](https://console.groq.com/) API key (primary LLM). Optionally a [Google AI Studio](https://aistudio.google.com/) key for the Gemini fallback.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_API_KEY=your_gemini_api_key_here   # optional fallback
SEMANTIC_SCHOLAR_API_KEY=your_s2_key_here # optional, improves resolution
DEMO_MODE=true
ALLOWED_ORIGINS=http://localhost:5173
```

> For real ORCID sign-in, set `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRET`; otherwise `DEMO_MODE=true` uses a mock ORCID identity.

Start the server:

```bash
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) — click **Continue with Demo Access** to enter without an account.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/api/search?q=` | Search for papers (returns candidates) |
| `GET` | `/api/profile` | Researcher profile from ORCID / open scholarly data |
| `GET` | `/api/routing/plan` | Field-aware source-routing plan for a paper |
| `POST` | `/api/analyze` | Runs the pipeline and returns draft sentences for curation |
| `POST` | `/api/compose` | Composes the final narrative from the reviewer-approved sentences |
| `POST` | `/api/evaluate` | Agentic vs baseline comparison |
| `POST` | `/api/ref/beta` | Generate REF 2029 case study |
| `GET` | `/api/stats` | Total analyses, avg faithfulness |
| `GET` | `/api/dataset?fmt=csv` | Export all analyses as CSV |
| `GET` | `/api/history` | User query history (auth required) |
| `POST` | `/api/auth/orcid/exchange` | ORCID OAuth code exchange |

---

## Sample Papers to Test

| Paper | Input |
|---|---|
| Attention Is All You Need | `Attention Is All You Need` |
| Deep learning (LeCun et al.) | `10.1038/nature14539` |
| AlphaFold | `10.1038/s41586-021-03819-2` |
| BERT | `10.18653/v1/N19-1423` |
| LIGO Gravitational Waves | `10.1103/PhysRevLett.116.061102` |
| CRISPR-Cas9 | `10.1126/science.1225829` |

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # API routes, CORS, rate limiting
│   │   ├── models.py            # Pydantic data schemas
│   │   ├── services.py          # LangGraph pipeline: routing, retrieval, downstream, draft/compose
│   │   ├── profile.py           # ORCID / OpenAlex researcher profiling
│   │   ├── domain_classifier.py # Field-aware source routing
│   │   ├── rag.py               # ChromaDB vector store + embeddings
│   │   ├── hf_synthesis.py      # Groq → Gemini interface, drafting, composition, references
│   │   ├── evaluation.py        # Agentic vs baseline comparison
│   │   ├── ref_beta.py          # REF 2029 writer + auditor agents
│   │   ├── database.py          # SQLite persistence
│   │   ├── access_guard.py      # Author identity verification / demo mode
│   │   ├── auth.py              # ORCID + LinkedIn JWT signing
│   │   └── validation.py        # Input sanitisation
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── Dashboard.tsx        # Main application + sentence-curation view
│       ├── LandingPage.tsx      # Marketing page
│       ├── LoginModal.tsx       # ORCID / multi-auth modal
│       ├── AuthContext.tsx      # Global auth state
│       ├── AuthCallback.tsx     # OAuth redirect handler
│       ├── brand.tsx            # REFlect AI brand assets
│       └── styles.css           # REFlect AI design system
│
└── docs/
    ├── reflect_ai_paper.tex     # Research paper (LNCS)
    └── screenshots/             # UI screenshots
```

---

## Security

- Input sanitisation blocks SQL injection, XSS, path traversal, and code injection patterns
- Per-IP sliding window rate limiting on every endpoint
- CORS restricted to configured origins
- API keys stored in `.env`, never exposed to the browser
- Author verification before REF case study generation

---

## Contributing

1. Fork the repository and create a feature branch
2. Install dependencies as described in **Run Locally**
3. Run tests: `pytest` (backend) · `npm test` (frontend)
4. Submit a pull request

---

*Built for research transparency — every claim is traceable to its source, and a human vouches for every one.*
