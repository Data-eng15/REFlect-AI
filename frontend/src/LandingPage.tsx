import React, { useState } from "react";
import { ArrowRight, ShieldCheck, BookOpen, Clock, Search, GitBranch } from "lucide-react";
import LoginModal from "./LoginModal";

/* ── Logo monogram ──────────────────────────────────────────────────────── */
function Logo({ size = 26 }: { size?: number }) {
  return (
    <div className="il-logo">
      <span className="il-logo-mark" style={{ fontSize: size }}>
        i<span className="il-logo-dot" style={{ width: Math.max(3, size / 10), height: Math.max(3, size / 10) }} />l
      </span>
      <span className="il-logo-wordmark" style={{ fontSize: size * 0.54 }}>Impact Lab</span>
    </div>
  );
}

/* ── Mini agent log for specimen card ──────────────────────────────────── */
const SPECIMEN_STEPS = [
  { state: "complete", label: "Retrieved 76,412 citations from OpenAlex", t: "1.2s" },
  { state: "complete", label: "Found 2,840 GitHub implementations", t: "0.9s" },
  { state: "running",  label: "Synthesising evidence via RAG", t: "…" },
];

function MiniAgentLog() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {SPECIMEN_STEPS.map((s, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 18, height: 18, borderRadius: "50%", flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: s.state === "complete" ? "var(--sage-100)" : s.state === "running" ? "var(--ochre-100)" : "var(--linen)",
              color: s.state === "complete" ? "var(--sage)" : s.state === "running" ? "var(--ochre)" : "var(--slate-300)",
            }}
          >
            {s.state === "complete" && (
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
            {s.state === "running" && <span className="running-dot" style={{ width: 6, height: 6 }} />}
          </div>
          <span style={{ flex: 1, fontSize: 12, lineHeight: "18px", color: s.state === "running" ? "var(--fg-1)" : "var(--fg-2)", fontWeight: s.state === "running" ? 500 : 400 }}>
            {s.label}
          </span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--fg-3)" }}>{s.t}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Specimen card (hero right) ─────────────────────────────────────────── */
function SpecimenCard() {
  return (
    <div className="specimen-card">
      <div className="specimen-header">
        <div className="specimen-meta">
          <div className="eyebrow">Impact summary · sample</div>
          <div className="specimen-title">Deep learning</div>
          <div className="specimen-doi">10.1038/nature14539 · LeCun, Bengio, Hinton · 2015</div>
        </div>
        <div className="specimen-score">
          <div className="specimen-score-val">0.92</div>
          <div className="specimen-score-label">Strong</div>
        </div>
      </div>

      <p className="specimen-body">
        The paper consolidates a decade of work on representation learning and remains a foundational reference across vision, language, and speech. Forward citations cluster heavily in computer vision and biomedical imaging, with sustained uptake in industrial research labs.
      </p>

      <div className="specimen-metrics">
        {[
          { label: "Citations", value: "76,412" },
          { label: "Repos",     value: "2,840" },
          { label: "Patents",   value: "38" },
        ].map(m => (
          <div key={m.label} style={{ padding: "12px 14px", background: "var(--linen)", borderRadius: "var(--r-sm)", display: "flex", flexDirection: "column", gap: 4 }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>{m.label}</div>
            <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, fontWeight: 500, letterSpacing: "-0.01em", color: "var(--ink)" }}>{m.value}</div>
          </div>
        ))}
      </div>

      <div className="specimen-divider">
        <div className="eyebrow">Agent reasoning</div>
        <MiniAgentLog />
      </div>
    </div>
  );
}

/* ── Capabilities grid ──────────────────────────────────────────────────── */
const CAPABILITIES = [
  ["Metadata retrieval",  "Resolves DOIs, titles, arXiv IDs through Crossref and OpenAlex; harmonises author lists, years, abstracts."],
  ["Citation tracking",   "Traces forward citations through Semantic Scholar and OpenAlex; clusters them by venue and topic."],
  ["Code & adoption",     "Searches GitHub for repository implementations and downstream forks signalling research adoption."],
  ["Policy & patents",    "Cross-references Google Patents and policy databases for industrial and governmental uptake."],
  ["RAG synthesis",       "Embeds retrieved passages in local ChromaDB and synthesises a 200-word, evidence-grounded summary."],
  ["Glass-box audit",     "Every claim is anchored to a retrieved source so reviewers can verify the chain of evidence."],
];

/* ── Main component ─────────────────────────────────────────────────────── */
export default function LandingPage() {
  const [showLogin, setShowLogin] = useState(false);

  return (
    <div className="landing-container">

      {/* Header */}
      <header className="landing-header">
        <Logo size={26} />
        <nav className="landing-nav">
          <a href="#how" className="nav-link">How it works</a>
          <a href="#sources" className="nav-link">Sources</a>
          <a href="#docs" className="nav-link">Documentation</a>
          <button className="btn btn-secondary" onClick={() => setShowLogin(true)}>Sign in</button>
        </nav>
      </header>

      {/* Hero */}
      <section className="landing-hero">
        <div className="hero-left">
          <div className="hero-badge">
            <span className="hero-badge-dot" />
            Now open to research institutions
          </div>

          <h1 className="hero-title">
            Autonomous research <em>impact</em> summariser.
          </h1>

          <p className="hero-subtitle">
            Trace a paper's downstream influence — citations, code, patents, policy, funding — through open research data, then synthesise the evidence into a 200-word impact summary.
          </p>

          <div className="hero-actions">
            <button className="btn btn-primary btn-lg" onClick={() => setShowLogin(true)}>
              Launch tool <ArrowRight size={15} />
            </button>
            <button className="btn btn-ghost btn-lg" onClick={() => setShowLogin(true)}>
              Read the methodology →
            </button>
          </div>

          <div className="hero-trust">
            <div className="hero-trust-item"><ShieldCheck size={13} /> Glass-box auditable</div>
            <div className="hero-trust-item"><BookOpen size={13} /> 200-word evidence summary</div>
            <div className="hero-trust-item"><Clock size={13} /> ~6s end-to-end</div>
          </div>
        </div>

        <SpecimenCard />
      </section>

      {/* Sources strip */}
      <section className="sources-strip" id="sources">
        <div className="sources-strip-inner">
          <div className="eyebrow">Retrieves from</div>
          {["OpenAlex", "Semantic Scholar", "Crossref", "GitHub", "Google Patents", "ORCID", "arXiv"].map(s => (
            <span key={s} className="sources-name">{s}</span>
          ))}
        </div>
      </section>

      {/* Capabilities */}
      <section className="capabilities-section" id="how">
        <div className="capabilities-grid">
          <div className="capabilities-intro">
            <div className="eyebrow">The system</div>
            <h2>An agent that reads, retrieves, and reasons — and shows its working.</h2>
            <p>Impact Lab coordinates five retrieval agents and a RAG synthesiser. Every claim in the final summary is traceable back to the source it came from.</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 4 }}>
              {[
                [Search, "Searches 7 open data sources autonomously"],
                [GitBranch, "Shows every reasoning step in the agent log"],
                [ShieldCheck, "Faithfulness score on every summary"],
              ].map(([Icon, text], i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "var(--fg-2)" }}>
                  {/* @ts-ignore */}
                  <Icon size={14} color="var(--accent)" />
                  {text as string}
                </div>
              ))}
            </div>
          </div>

          <div className="capabilities-cells">
            {CAPABILITIES.map(([title, body]) => (
              <div key={title} className="capability-cell">
                <div className="eyebrow" style={{ color: "var(--accent)", marginBottom: 8 }}>{title}</div>
                <p style={{ fontSize: 14, lineHeight: "22px", color: "var(--fg-1)" }}>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA strip */}
      <section className="cta-strip">
        <div className="cta-strip-inner">
          <div>
            <div className="cta-heading">Ready to trace a paper?</div>
            <div className="cta-sub">Sign in with email, or with your institution / ORCID iD.</div>
          </div>
          <button className="btn btn-primary btn-lg" onClick={() => setShowLogin(true)}>
            Access system <ArrowRight size={15} />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-left">
          <Logo size={20} />
          <span className="footer-copy">© 2026 Impact Lab — Research transparency tooling.</span>
        </div>
        <div className="footer-links">
          <a href="#">Privacy</a>
          <a href="#">Methodology</a>
          <a href="#">GitHub</a>
        </div>
      </footer>

      {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}
    </div>
  );
}
