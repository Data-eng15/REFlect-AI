import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight, User, Lock, Mail, Linkedin, GraduationCap, Building2,
  ShieldCheck, Scale, Search, TrendingUp, Code2, Landmark, BrainCircuit,
  ChevronDown, Plus,
} from "lucide-react";
import { useAuth } from "./AuthContext";
import { Logo, OrcidMark, ORCID_GREEN, Eyebrow } from "./brand";

/* ── Primitives ───────────────────────────────────────────────────────────── */

function Button({
  variant = "primary", size = "md", children, icon, iconRight, style, ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost"; size?: "md" | "lg"; icon?: React.ReactNode; iconRight?: React.ReactNode;
}) {
  const variants: Record<string, React.CSSProperties> = {
    primary: { background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" },
    secondary: { background: "#fff", borderColor: "var(--rule-strong)", color: "var(--fg-1)" },
    ghost: { background: "transparent", color: "var(--accent)", borderColor: "transparent" },
  };
  return (
    <button
      {...rest}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
        fontFamily: "var(--font-sans)", fontWeight: 500, lineHeight: "20px",
        border: "1px solid transparent", borderRadius: 6, cursor: "pointer",
        transition: "background 120ms var(--ease), border-color 120ms var(--ease), color 120ms var(--ease)",
        fontSize: size === "lg" ? 14 : 13, padding: size === "lg" ? "12px 20px" : "10px 16px",
        whiteSpace: "nowrap", ...variants[variant], ...style,
      }}
      onMouseOver={(e) => {
        if (variant === "primary") e.currentTarget.style.background = "var(--accent-hover)";
        if (variant === "secondary") { e.currentTarget.style.background = "var(--accent-softer)"; e.currentTarget.style.borderColor = "var(--accent)"; }
        if (variant === "ghost") e.currentTarget.style.background = "var(--accent-softer)";
      }}
      onMouseOut={(e) => {
        const v = variants[variant];
        e.currentTarget.style.background = v.background as string;
        e.currentTarget.style.borderColor = (v.borderColor as string) || "transparent";
      }}
    >
      {icon}{children}{iconRight}
    </button>
  );
}

function Field({
  label, icon, value, onChange, type = "text", placeholder, mono, autoFocus, name, optional,
}: {
  label?: string; icon?: React.ReactNode; value: string; onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  type?: string; placeholder?: string; mono?: boolean; autoFocus?: boolean; name?: string; optional?: boolean;
}) {
  const [focus, setFocus] = useState(false);
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {label && (
        <span style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-1)" }}>{label}</span>
          {optional && <span style={{ fontSize: 11, color: "var(--fg-3)" }}>optional</span>}
        </span>
      )}
      <div style={{
        display: "flex", alignItems: "center", gap: 10, background: "#fff", borderRadius: 6,
        border: focus ? "2px solid var(--accent)" : "1px solid var(--rule)",
        boxShadow: focus ? "0 0 0 4px var(--indigo-100)" : "none",
        padding: focus ? "9px 11px" : "10px 12px",
        transition: "box-shadow 120ms var(--ease), border-color 120ms var(--ease)",
      }}>
        {icon && <span style={{ display: "inline-flex", color: "var(--fg-3)" }}>{icon}</span>}
        <input
          name={name} type={type} placeholder={placeholder} value={value} onChange={onChange} autoFocus={autoFocus}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          style={{
            flex: 1, border: 0, outline: "none", background: "transparent",
            fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
            fontSize: 14, lineHeight: "22px", color: "var(--fg-1)", minWidth: 0,
          }}
        />
      </div>
    </label>
  );
}

function ProviderButton({ icon, children, onClick, accent }: {
  icon: React.ReactNode; children: React.ReactNode; onClick: () => void; accent?: string;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
        width: "100%", padding: "11px 16px", borderRadius: 6, cursor: "pointer",
        border: "1px solid var(--rule-strong)", background: "#fff",
        fontFamily: "var(--font-sans)", fontSize: 14, fontWeight: 500, color: "var(--fg-1)",
        transition: "background 120ms var(--ease), border-color 120ms var(--ease)",
      }}
      onMouseOver={(e) => { e.currentTarget.style.background = "var(--linen)"; e.currentTarget.style.borderColor = "var(--slate-300)"; }}
      onMouseOut={(e) => { e.currentTarget.style.background = "#fff"; e.currentTarget.style.borderColor = "var(--rule-strong)"; }}
    >
      <span style={{ display: "inline-flex", color: accent || "var(--fg-2)" }}>{icon}</span>
      {children}
    </button>
  );
}

function OrDivider({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--fg-3)" }}>
      <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
      <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" }}>{children}</span>
      <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
    </div>
  );
}

/* ── Auth cards ───────────────────────────────────────────────────────────── */

function AuthCard({ onOrcid }: { onOrcid: () => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <h2 style={{ fontFamily: "var(--font-serif)", fontSize: 26, lineHeight: "32px", fontWeight: 500, letterSpacing: "-0.01em", color: "var(--ink)" }}>Sign in to REFlect AI</h2>
        <div style={{ fontSize: 14, color: "var(--fg-2)", lineHeight: "22px" }}>
          Your ORCID iD is your account — it verifies your identity and automatically links your publication record. No separate sign-up or password needed.
        </div>
      </div>

      <ProviderButton icon={<OrcidMark />} accent={ORCID_GREEN} onClick={onOrcid}>Sign in with ORCID iD</ProviderButton>

      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--fg-3)", lineHeight: "18px" }}>
        <ShieldCheck size={14} />
        <span>Secure academic sign-in via ORCID — we never see or store a password.</span>
      </div>

      <div style={{ fontSize: 13, color: "var(--fg-2)", textAlign: "center" }}>
        Don't have an ORCID iD?{" "}
        <a href="https://orcid.org/register" target="_blank" rel="noreferrer" style={{ fontWeight: 500 }}>Create one free</a> — it takes a minute.
      </div>
    </div>
  );
}

/* ── Landing page ─────────────────────────────────────────────────────────── */

export default function LandingPage() {
  const navigate = useNavigate();
  const { loginWithOrcid } = useAuth();

  const handleOrcid = async () => {
    try {
      const signedIn = await loginWithOrcid();
      if (signedIn) navigate("/dashboard");
      // otherwise the browser is redirecting to ORCID's authorize page
    } catch (e) {
      console.error("ORCID sign-in failed", e);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "20px 48px", borderBottom: "1px solid var(--rule)",
        position: "sticky", top: 0, background: "rgba(252,252,250,0.85)", backdropFilter: "blur(8px)", zIndex: 10,
      }}>
        <Logo size={24} />
        <nav style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <a href="#how" style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-2)", textDecoration: "none" }}>How it works</a>
          <a href="#sources" style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-2)", textDecoration: "none" }}>Data sources</a>
          <a href="#" onClick={(e) => e.preventDefault()} style={{ fontSize: 13, fontWeight: 500, color: "var(--fg-2)", textDecoration: "none" }}>Methodology</a>
          <Button onClick={handleOrcid}>Sign in with ORCID</Button>
        </nav>
      </header>

      {/* Hero + auth */}
      <section style={{
        maxWidth: "var(--container)", width: "100%", margin: "0 auto",
        padding: "80px 48px 64px", display: "grid", gridTemplateColumns: "1.05fr 0.95fr", gap: 64, alignItems: "flex-start",
      }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 24, paddingTop: 8 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 12px", borderRadius: 999, border: "1px solid var(--rule)", background: "#fff", width: "max-content", fontSize: 12, color: "var(--fg-2)" }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--accent)" }} />
            Built for REF impact case studies
          </div>

          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 56, lineHeight: "62px", fontWeight: 500, letterSpacing: "-0.02em", color: "var(--ink)", textWrap: "balance" }}>
            Trace the <em style={{ color: "var(--accent)", fontStyle: "italic" }}>real-world impact</em> of your research.
          </h1>

          <p style={{ fontSize: 18, lineHeight: "30px", color: "var(--fg-2)", maxWidth: 520, textWrap: "pretty" }}>
            REFlect AI follows a paper's downstream influence — citations, code adoption, patents, policy uptake, and funding — across open research data, then synthesises the evidence into a REF-ready impact narrative.
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: 20, marginTop: 4, fontSize: 13, color: "var(--fg-2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}><ShieldCheck size={16} /> Every claim traceable to source</div>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}><Scale size={16} /> REF 2029 aligned</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 1, background: "var(--rule)", border: "1px solid var(--rule)", borderRadius: 10, overflow: "hidden", marginTop: 8 }}>
            {[["1,400+", "Sources indexed"], ["~6s", "End-to-end analysis"], ["0.81", "Avg. faithfulness"]].map(([v, l]) => (
              <div key={l} style={{ background: "#fff", padding: "16px 18px", display: "flex", flexDirection: "column", gap: 4 }}>
                <div style={{ fontFamily: "var(--font-serif)", fontSize: 24, fontWeight: 500, color: "var(--ink)" }}>{v}</div>
                <Eyebrow style={{ fontSize: 10 }}>{l}</Eyebrow>
              </div>
            ))}
          </div>
        </div>

        {/* Auth card */}
        <div style={{ background: "#fff", border: "1px solid var(--rule)", borderRadius: 14, padding: 32, boxShadow: "var(--shadow-card)", position: "sticky", top: 96 }}>
          <AuthCard onOrcid={handleOrcid} />

        </div>
      </section>

      {/* Sources strip */}
      <section id="sources" style={{ borderTop: "1px solid var(--rule)", borderBottom: "1px solid var(--rule)", background: "var(--linen)" }}>
        <div style={{ maxWidth: "var(--container)", margin: "0 auto", padding: "20px 48px", display: "flex", alignItems: "center", gap: 28, flexWrap: "wrap" }}>
          <Eyebrow>Retrieves from</Eyebrow>
          {["OpenAlex", "Semantic Scholar", "Crossref", "GitHub", "Google Patents", "UKRI Gateway", "Europe PMC", "ORCID"].map((s) => (
            <span key={s} style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: 17, color: "var(--fg-1)" }}>{s}</span>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" style={{ maxWidth: "var(--container)", width: "100%", margin: "0 auto", padding: "72px 48px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 2fr", gap: 48, alignItems: "flex-start" }}>
          <div>
            <Eyebrow>How it works</Eyebrow>
            <h2 style={{ fontFamily: "var(--font-serif)", fontSize: 32, lineHeight: "40px", fontWeight: 500, letterSpacing: "-0.01em", marginTop: 12, color: "var(--ink)" }}>
              An agent that reads, retrieves, and reasons — and shows its working.
            </h2>
            <p style={{ fontSize: 16, lineHeight: "26px", color: "var(--fg-2)", marginTop: 16, maxWidth: 420 }}>
              REFlect AI coordinates five retrieval agents and a RAG synthesiser. Every sentence in the final narrative is anchored to the source it came from, so reviewers can audit the chain of evidence.
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--rule)", border: "1px solid var(--rule)", borderRadius: 10, overflow: "hidden" }}>
            {([
              [<Search size={18} />, "Metadata retrieval", "Resolves DOIs, titles, and arXiv IDs through Crossref and OpenAlex; harmonises authors, years, and abstracts."],
              [<TrendingUp size={18} />, "Citation tracking", "Traces forward citations through Semantic Scholar and OpenAlex; clusters them by venue and topic."],
              [<Code2 size={18} />, "Code & adoption", "Searches GitHub for implementations and downstream forks signalling research adoption."],
              [<Landmark size={18} />, "Policy & patents", "Cross-references Google Patents and policy databases for industrial and governmental uptake."],
              [<BrainCircuit size={18} />, "RAG synthesis", "Embeds retrieved passages in a local vector store and drafts an evidence-grounded impact narrative."],
              [<ShieldCheck size={18} />, "Glass-box audit", "Every claim is anchored to a retrieved source so REF reviewers can verify the evidence."],
            ] as [React.ReactNode, string, string][]).map(([ic, t, b]) => (
              <div key={t} style={{ background: "#fff", padding: "24px 24px 28px", display: "flex", flexDirection: "column", gap: 12 }}>
                <span style={{ color: "var(--accent)" }}>{ic}</span>
                <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink)" }}>{t}</div>
                <p style={{ fontSize: 14, lineHeight: "22px", color: "var(--fg-2)" }}>{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ padding: "28px 48px", borderTop: "1px solid var(--rule)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Logo size={20} />
          <span style={{ fontSize: 12, color: "var(--fg-3)" }}>© 2026 REFlect AI — Research impact intelligence.</span>
        </div>
        <div style={{ display: "flex", gap: 20, fontSize: 12, color: "var(--fg-3)" }}>
          <a href="#" onClick={(e) => e.preventDefault()} style={{ color: "inherit", textDecoration: "none" }}>Privacy</a>
          <a href="#" onClick={(e) => e.preventDefault()} style={{ color: "inherit", textDecoration: "none" }}>Methodology</a>
          <a href="#" onClick={(e) => e.preventDefault()} style={{ color: "inherit", textDecoration: "none" }}>Contact</a>
        </div>
      </footer>
    </div>
  );
}
