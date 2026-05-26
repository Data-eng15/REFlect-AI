import React, { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  Check,
  ChevronDown,
  Clock,
  Code2,
  Coins,
  Database,
  Download,
  ExternalLink,
  FileText,
  GraduationCap,
  Globe,
  Landmark,
  Loader2,
  LogOut,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

// ─── Types ──────────────────────────────────────────────────────────────────

type AgentState = "pending" | "running" | "complete" | "warning" | "error";

type AgentStatus = {
  name: string;
  label: string;
  state: AgentState;
  detail: string;
};

type TraceLog = {
  timestamp: string;
  agent: string;
  message: string;
  data: Record<string, unknown>;
};

type PaperMetadata = {
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  abstract: string | null;
  source_url: string | null;
};

type EvidenceItem = {
  title: string;
  url: string | null;
  year: number | null;
  authors: string[];
  snippet: string | null;
  source: string;
  kind: "citation" | "code" | "full_text" | "funding" | "patent" | "policy" | "grant" | string;
  citation_count: number | null;
  metric_label: string | null;
  metric_value: string | null;
};

type ImpactSection = {
  title: string;
  body: string;
};

type AccessCheck = {
  allowed: boolean;
  verified: boolean;
  demo_mode: boolean;
  matched_author: string | null;
  score: number;
  paper_authors: string[];
  reason: string;
};

type AnalyzeResponse = {
  metadata: PaperMetadata;
  summary: string;
  sections: ImpactSection[];
  evidence: EvidenceItem[];
  agent_statuses: AgentStatus[];
  logs: TraceLog[];
  faithfulness_score: number;
  citation_count: number;
  topics: string[];
  model_provider: string;
  rag_context_count: number;
  guardrail_status: string;
  limitations: string[];
  ref_report: string;
  access?: AccessCheck;
};

type SiteStats = {
  total_analyses: number;
  avg_faithfulness: number;
  avg_citations: number;
};

type SearchCandidate = {
  doi: string | null;
  title: string;
  authors: string[];
  year: number | null;
  venue: string;
  type: string;
  url: string | null;
};

type EvalSide = {
  approach: string;
  summary: string;
  citation_count: number;
  evidence_count: number;
  sources_used: string[];
  word_count: number;
  faithfulness_score: number;
  elapsed_seconds: number | null;
  rag_contexts?: number;
};

type EvalComparison = {
  query: string;
  agentic: EvalSide;
  baseline: EvalSide;
  verdict: string;
  agentic_full?: AnalyzeResponse;
};

type VerificationFlag = {
  claim: string;
  section: string;
  reason: string;
  severity: "warning" | "critical";
};

type WordCounts = {
  total: number;
  summary: number;
  research: number;
  impact: number;
  total_ok: boolean;
  summary_ok: boolean;
  research_ok: boolean;
  impact_ok: boolean;
};

type BetaRefResult = {
  case_study: string;
  flags: VerificationFlag[];
  word_counts: WordCounts;
  access?: AccessCheck;
  error?: string;
};

// ─── Constants ───────────────────────────────────────────────────────────────

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const SAMPLE_QUERIES = [
  "10.1038/nature14539",
  "Attention Is All You Need",
  "10.1145/3292500.3330701",
];

const DATA_SOURCES = [
  "CrossRef", "Semantic Scholar", "GitHub", "Europe PMC",
  "OpenAlex", "USPTO Patents", "UKRI Gateway",
];

const INITIAL_STATUSES: AgentStatus[] = [
  { name: "supervisor",  label: "Supervisor",  state: "pending", detail: "Ready" },
  { name: "metadata",   label: "Metadata",    state: "pending", detail: "Ready" },
  { name: "scholar",    label: "Scholar",     state: "pending", detail: "Ready" },
  { name: "content",    label: "Content",     state: "pending", detail: "Ready" },
  { name: "code",       label: "Code",        state: "pending", detail: "Ready" },
  { name: "rag",        label: "RAG",         state: "pending", detail: "Ready" },
  { name: "guardrail",  label: "Guardrail",   state: "pending", detail: "Ready" },
  { name: "impact",     label: "Impact",      state: "pending", detail: "Ready" },
  { name: "synthesis",  label: "Synthesis",   state: "pending", detail: "Ready" },
];

const EVIDENCE_FILTERS = [
  { key: "all",       label: "All" },
  { key: "citation",  label: "Citations" },
  { key: "code",      label: "Code" },
  { key: "patent",    label: "Patents" },
  { key: "policy",    label: "Policy" },
  { key: "grant",     label: "Grants" },
  { key: "funding",   label: "Funding" },
  { key: "full_text", label: "Full text" },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatAuthors(authors: string[]): string {
  if (!authors || !authors.length) return "Unknown authors";
  if (authors.length <= 3) return authors.join(", ");
  return `${authors.slice(0, 3).join(", ")} et al.`;
}

function scoreClass(score: number): string {
  if (score >= 0.85) return "strong";
  if (score >= 0.7) return "moderate";
  return "weak";
}

function scoreLabel(score: number): string {
  if (score >= 0.85) return "Strong";
  if (score >= 0.7) return "Developing";
  return "Needs evidence";
}

function agentIcon(name: string): React.ReactNode {
  const icons: Record<string, React.ReactNode> = {
    supervisor: <BrainCircuit size={14} />,
    metadata:   <Database size={14} />,
    scholar:    <GraduationCap size={14} />,
    content:    <FileText size={14} />,
    code:       <Code2 size={14} />,
    rag:        <BookOpen size={14} />,
    guardrail:  <ShieldCheck size={14} />,
    impact:     <Sparkles size={14} />,
    synthesis:  <Globe size={14} />,
  };
  return icons[name] ?? <Globe size={14} />;
}

function stepClass(state: AgentState): string {
  return `agent-step ${state}`;
}

function renderMarkdown(text: string): React.ReactNode {
  if (!text) return null;
  const lines = text.split("\n");
  return lines.map((line, i) => {
    if (line.startsWith("### ")) return <h3 key={i} className="ref-section-title">{line.replace(/^###\s*/, "")}</h3>;
    if (line.startsWith("## "))  return <h2 key={i} className="ref-section-title">{line.replace(/^##\s*/, "")}</h2>;
    if (line.startsWith("# "))   return <h2 key={i} className="ref-section-title">{line.replace(/^#\s*/, "")}</h2>;
    if (line.startsWith("- ") || line.startsWith("* ")) return <p key={i} className="ref-list-item">{line.replace(/^[-*]\s*/, "• ")}</p>;
    if (/^\d+\.\s/.test(line)) return <p key={i} className="ref-list-item">{line}</p>;
    if (!line.trim()) return <br key={i} />;
    return <p key={i} className="ref-paragraph">{line}</p>;
  });
}

function downloadReport(content: string, filename: string) {
  const htmlContent = `<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
<head><meta charset='utf-8'><title>REF Impact Case Study</title></head>
<body style='font-family:Calibri,sans-serif;font-size:11pt;line-height:1.6'>
${content.split("\n").map(line => {
  if (line.startsWith("### ")) return `<h3 style='color:#4F46E5'>${line.replace(/^###\s*/,"")}</h3>`;
  if (line.startsWith("## "))  return `<h2>${line.replace(/^##\s*/,"")}</h2>`;
  if (line.startsWith("- ") || line.startsWith("* ")) return `<p style='margin-left:20px'>• ${line.replace(/^[-*]\s*/,"")}</p>`;
  if (/^\d+\.\s/.test(line)) return `<p style='margin-left:20px'>${line}</p>`;
  if (!line.trim()) return "<br/>";
  return `<p>${line}</p>`;
}).join("")}
</body></html>`;
  const blob = new Blob([htmlContent], { type: "application/msword" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

function withActiveStatuses(statuses: AgentStatus[]): AgentStatus[] {
  if (statuses.some(s => s.state === "running")) return statuses;
  return statuses.map((s, i) => i === 0 ? { ...s, state: "running", detail: "Starting…" } : s);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Logo() {
  return (
    <div className="il-logo">
      <span className="il-logo-mark" style={{ fontSize: 24 }}>
        i<span className="il-logo-dot" style={{ width: 4, height: 4 }} />l
      </span>
      <span className="il-logo-wordmark" style={{ fontSize: 13 }}>Impact Lab</span>
    </div>
  );
}

function StatusIcon({ state }: { state: AgentState }) {
  if (state === "complete") return <Check size={14} />;
  if (state === "running") return <Loader2 size={14} className="spin" />;
  if (state === "warning" || state === "error") return <AlertTriangle size={14} />;
  return <span className="step-dot" />;
}

function AgentLogPanel({ statuses }: { statuses: AgentStatus[] }) {
  return (
    <div className="agent-log-panel">
      {statuses.map((s, i) => (
        <div key={s.name} className="agent-step">
          <div className={`agent-nub ${s.state}`}>
            {s.state === "complete" && <Check size={11} />}
            {s.state === "running"  && <span className="running-dot" />}
            {s.state === "error"    && <AlertTriangle size={11} />}
            {(s.state === "pending" || s.state === "warning") && <span style={{ width: 5, height: 5, borderRadius: "50%", background: "currentColor", display: "inline-block" }} />}
          </div>
          <div className="agent-step-content">
            <div className={`agent-step-label ${s.state}`}>{s.label}</div>
            {s.detail && s.detail !== "Ready" && (
              <div className="agent-step-detail">{s.detail}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function AuthorBadge({ access }: { access: AccessCheck }) {
  if (access.verified) {
    return (
      <div className="author-badge verified">
        <ShieldCheck size={13} />
        Author verified: {access.matched_author} (score {access.score})
      </div>
    );
  }
  if (access.demo_mode) {
    return (
      <div className="author-badge demo">
        <AlertTriangle size={13} />
        Demo mode — {access.reason}
      </div>
    );
  }
  return (
    <div className="author-badge blocked">
      <AlertTriangle size={13} />
      Access restricted — {access.reason}
    </div>
  );
}

function OverviewTab({
  result, loading, openSections, setOpenSections,
}: {
  result: AnalyzeResponse;
  loading: boolean;
  openSections: Record<string, boolean>;
  setOpenSections: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
}) {
  const statuses = loading ? withActiveStatuses(result.agent_statuses ?? INITIAL_STATUSES) : (result.agent_statuses ?? INITIAL_STATUSES);
  const ev = result.evidence ?? [];
  const citCount   = ev.filter(e => e.kind === "citation").length;
  const codeCount  = ev.filter(e => e.kind === "code").length;
  const patCount   = ev.filter(e => e.kind === "patent").length;
  const polCount   = ev.filter(e => e.kind === "policy").length;
  const grantCount = ev.filter(e => e.kind === "grant").length;
  const fundCount  = ev.filter(e => e.kind === "funding").length;
  const topicCount = result.topics?.length ?? 0;
  const total = Math.max(1, citCount + codeCount + patCount + polCount + grantCount + fundCount);

  return (
    <div className="overview-grid">
      {/* Left column */}
      <div className="overview-left">
        <div className="paper-header-block">
          <div className="paper-title-wrap">
            <p className="eyebrow">Impact Summary</p>
            <h2 className="paper-title">{result.metadata.title}</h2>
            <p className="paper-meta">
              {formatAuthors(result.metadata.authors)}
              {result.metadata.year ? ` · ${result.metadata.year}` : ""}
              {result.metadata.doi ? (
                <> · <a href={`https://doi.org/${result.metadata.doi}`} target="_blank" rel="noreferrer" className="doi-link">{result.metadata.doi}</a></>
              ) : null}
            </p>
          </div>
          <div className={`faith-chip ${scoreClass(result.faithfulness_score)}`}>
            <span className="faith-score">{result.faithfulness_score.toFixed(2)}</span>
            <span className="faith-label">{scoreLabel(result.faithfulness_score)}</span>
          </div>
        </div>

        {result.access && <AuthorBadge access={result.access} />}

        <div className="summary-block">
          <p className="summary-text">{result.summary}</p>
        </div>

        {result.topics && result.topics.length > 0 && (
          <div className="topics-row">
            {result.topics.map(t => <span key={t} className="topic-chip">{t}</span>)}
          </div>
        )}

        <div className="runtime-row">
          <span className="runtime-chip">Model: {result.model_provider}</span>
          <span className="runtime-chip">Guardrail: {result.guardrail_status}</span>
        </div>

        {result.sections && result.sections.length > 0 && (
          <div className="section-list">
            {result.sections.map(section => (
              <div className="fold-section" key={section.title}>
                <button
                  className="fold-trigger"
                  onClick={() => setOpenSections(prev => ({ ...prev, [section.title]: !prev[section.title] }))}
                >
                  <ChevronDown size={16} className={openSections[section.title] ? "chevron open" : "chevron"} />
                  {section.title}
                </button>
                {openSections[section.title] && (
                  <div className="fold-body">{section.body}</div>
                )}
              </div>
            ))}
          </div>
        )}

        {result.limitations && result.limitations.length > 0 && (
          <div className="limitations-panel">
            <div className="limitations-header">
              <AlertTriangle size={16} />
              <span>Current limitations</span>
            </div>
            {result.limitations.map(lim => (
              <div key={lim} className="limitation-item">{lim}</div>
            ))}
          </div>
        )}

        {result.access && !result.access.verified && result.access.demo_mode && (
          <div className="security-notice">
            <ShieldCheck size={14} />
            <span>Running in demo mode. Author identity not verified — full REF document generation requires sign-in with a verified author account.</span>
          </div>
        )}
      </div>

      {/* Right column */}
      <div className="overview-right">
        <div className="metrics-grid">
          <div className="metric-card">
            <GraduationCap size={16} className="metric-icon" />
            <span className="metric-val">{result.citation_count ? result.citation_count.toLocaleString() : "—"}</span>
            <span className="metric-lbl">Citations</span>
          </div>
          <div className="metric-card">
            <FileText size={16} className="metric-icon" />
            <span className="metric-val">{ev.length}</span>
            <span className="metric-lbl">Evidence items</span>
          </div>
          <div className="metric-card">
            <Code2 size={16} className="metric-icon" />
            <span className="metric-val">{codeCount}</span>
            <span className="metric-lbl">Code leads</span>
          </div>
          <div className="metric-card">
            <Database size={16} className="metric-icon" />
            <span className="metric-val">{result.rag_context_count}</span>
            <span className="metric-lbl">RAG chunks</span>
          </div>
          <div className="metric-card">
            <Landmark size={16} className="metric-icon" />
            <span className="metric-val">{patCount}</span>
            <span className="metric-lbl">Patents</span>
          </div>
          <div className="metric-card">
            <Globe size={16} className="metric-icon" />
            <span className="metric-val">{polCount}</span>
            <span className="metric-lbl">Policy refs</span>
          </div>
          <div className="metric-card">
            <Coins size={16} className="metric-icon" />
            <span className="metric-val">{grantCount + fundCount}</span>
            <span className="metric-lbl">Grants/Funding</span>
          </div>
          <div className="metric-card">
            <Sparkles size={16} className="metric-icon" />
            <span className="metric-val">{topicCount}</span>
            <span className="metric-lbl">Topics</span>
          </div>
        </div>

        <div className="ev-dist-section">
          <p className="ev-dist-title">Evidence distribution</p>
          <div className="evidence-dist-bar">
            {citCount > 0  && <div className="dist-seg citation"  style={{ width: `${(citCount/total)*100}%`  }} title={`Citations: ${citCount}`} />}
            {codeCount > 0 && <div className="dist-seg code"      style={{ width: `${(codeCount/total)*100}%` }} title={`Code: ${codeCount}`} />}
            {patCount > 0  && <div className="dist-seg patent"    style={{ width: `${(patCount/total)*100}%`  }} title={`Patents: ${patCount}`} />}
            {polCount > 0  && <div className="dist-seg policy"    style={{ width: `${(polCount/total)*100}%`  }} title={`Policy: ${polCount}`} />}
            {grantCount > 0 && <div className="dist-seg grant"   style={{ width: `${(grantCount/total)*100}%` }} title={`Grants: ${grantCount}`} />}
            {fundCount > 0 && <div className="dist-seg funding"   style={{ width: `${(fundCount/total)*100}%` }} title={`Funding: ${fundCount}`} />}
          </div>
          <div className="dist-legend">
            {citCount > 0   && <span><span className="dist-dot citation"/>Citations ({citCount})</span>}
            {codeCount > 0  && <span><span className="dist-dot code"/>Code ({codeCount})</span>}
            {patCount > 0   && <span><span className="dist-dot patent"/>Patents ({patCount})</span>}
            {polCount > 0   && <span><span className="dist-dot policy"/>Policy ({polCount})</span>}
            {grantCount > 0 && <span><span className="dist-dot grant"/>Grants ({grantCount})</span>}
            {fundCount > 0  && <span><span className="dist-dot funding"/>Funding ({fundCount})</span>}
          </div>
        </div>

        <AgentLogPanel statuses={statuses} />
      </div>
    </div>
  );
}

function EvidenceTab({ evidence, filter, setFilter }: {
  evidence: EvidenceItem[];
  filter: string;
  setFilter: (f: string) => void;
}) {
  const kindCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of evidence) m.set(e.kind, (m.get(e.kind) ?? 0) + 1);
    return m;
  }, [evidence]);

  const filtered = useMemo(() =>
    filter === "all" ? evidence : evidence.filter(e => e.kind === filter),
    [evidence, filter]
  );

  return (
    <div className="evidence-tab">
      <div className="evidence-filter-bar">
        {EVIDENCE_FILTERS.map(f => {
          const count = f.key === "all" ? evidence.length : (kindCounts.get(f.key) ?? 0);
          if (f.key !== "all" && count === 0) return null;
          return (
            <button
              key={f.key}
              className={`filter-pill ${filter === f.key ? "active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label} <span className="filter-count">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="evidence-grid">
        {filtered.map((item, i) => (
          <div key={i} className="evidence-card">
            <div className="evidence-card-top">
              <span className={`kind-tag ${item.kind}`}>{item.kind.replace("_", " ")}</span>
              {item.url && (
                <a href={item.url} target="_blank" rel="noreferrer" className="ev-ext-link">
                  <ExternalLink size={13} />
                </a>
              )}
            </div>
            <h4 className="ev-title">{item.title}</h4>
            <p className="ev-meta">
              {item.source}
              {item.authors && item.authors.length > 0 ? ` · ${formatAuthors(item.authors)}` : ""}
              {item.year ? ` · ${item.year}` : ""}
            </p>
            {item.metric_label && item.metric_value && (
              <span className="ev-metric">{item.metric_label}: {item.metric_value}</span>
            )}
            {item.snippet && <em className="ev-snippet">"{item.snippet}"</em>}
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="empty-evidence">
            <FileText size={24} />
            No evidence in this category.
          </div>
        )}
      </div>
    </div>
  );
}

function RefReportTab({ refReport, doi }: { refReport: string; doi: string | null }) {
  const wordCount = refReport.split(/\s+/).filter(Boolean).length;
  return (
    <div className="ref-tab">
      <div className="ref-tab-header">
        <div>
          <h3>REF Impact Case Study</h3>
          <p className="ref-tab-sub">{wordCount.toLocaleString()} words · Research England format</p>
        </div>
        <button
          className="btn-primary"
          onClick={() => downloadReport(refReport, `REF_Case_Study_${(doi || "report").replace(/\//g,"_")}.doc`)}
        >
          <Download size={14} /> Download .doc
        </button>
      </div>
      <div className="ref-body">
        {renderMarkdown(refReport)}
      </div>
    </div>
  );
}

function DebugLogsTab({ logs }: { logs: TraceLog[] }) {
  return (
    <div className="debug-tab">
      <table className="debug-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Agent</th>
            <th>Message</th>
            <th>Data</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, i) => (
            <tr key={i}>
              <td className="log-time">{log.timestamp}</td>
              <td><span className="log-agent-badge">{log.agent}</span></td>
              <td className="log-message">{log.message}</td>
              <td className="log-data">
                {Object.keys(log.data).length > 0
                  ? <code>{JSON.stringify(log.data, null, 0).slice(0, 80)}</code>
                  : <span className="log-empty">—</span>}
              </td>
            </tr>
          ))}
          {logs.length === 0 && (
            <tr><td colSpan={4} className="log-empty-row">No logs yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function EvalTab({ result, loading, error }: {
  result: EvalComparison | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <div className="eval-loading">
        <Loader2 size={28} className="spin" />
        <p>Running agentic vs. baseline comparison…</p>
        <span>This re-runs the full pipeline alongside a CrossRef-only baseline.</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="eval-error">
        <AlertTriangle size={18} />
        Evaluation failed: {error}
      </div>
    );
  }
  if (!result) {
    return (
      <div className="eval-empty">
        <BrainCircuit size={28} />
        <p>Click "Force Evaluate" to run the agentic vs. baseline comparison.</p>
      </div>
    );
  }

  const ag = result.agentic;
  const bl = result.baseline;
  const agWins = ag.faithfulness_score >= bl.faithfulness_score;

  return (
    <div className="eval-tab">
      <div className={`verdict-banner ${agWins ? "agentic-wins" : "baseline-wins"}`}>
        <BrainCircuit size={16} />
        <strong>Verdict:</strong> {result.verdict}
      </div>

      <div className="eval-comparison">
        <table className="eval-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Agentic Pipeline</th>
              <th>Baseline (CrossRef only)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Faithfulness score</td>
              <td>
                <span className={`eval-score-pill ${ag.faithfulness_score >= bl.faithfulness_score ? "winner" : ""}`}>
                  {ag.faithfulness_score.toFixed(2)}
                </span>
              </td>
              <td>
                <span className={`eval-score-pill ${bl.faithfulness_score > ag.faithfulness_score ? "winner" : ""}`}>
                  {bl.faithfulness_score.toFixed(2)}
                </span>
              </td>
            </tr>
            <tr>
              <td>Evidence items</td>
              <td><strong>{ag.evidence_count}</strong></td>
              <td>{bl.evidence_count}</td>
            </tr>
            <tr>
              <td>Sources used</td>
              <td>{ag.sources_used.join(", ") || "—"}</td>
              <td>{bl.sources_used?.join(", ") || "—"}</td>
            </tr>
            <tr>
              <td>Summary length</td>
              <td>{ag.word_count} words</td>
              <td>{bl.word_count} words</td>
            </tr>
            <tr>
              <td>RAG contexts</td>
              <td>{ag.rag_contexts ?? "—"}</td>
              <td>0</td>
            </tr>
            <tr>
              <td>Elapsed</td>
              <td>{ag.elapsed_seconds != null ? `${ag.elapsed_seconds}s` : "—"}</td>
              <td>{bl.elapsed_seconds != null ? `${bl.elapsed_seconds}s` : "—"}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="eval-summaries">
        <div className="eval-summary-card">
          <div className="eval-summary-head">
            <BrainCircuit size={14} /> Agentic summary
          </div>
          <p>{ag.summary}</p>
        </div>
        <div className="eval-summary-card baseline">
          <div className="eval-summary-head">
            <Globe size={14} /> Baseline summary
          </div>
          <p>{bl.summary}</p>
        </div>
      </div>
    </div>
  );
}

function WordBar({ label, value, min, max, ok }: {
  label: string; value: number; min: number; max: number; ok: boolean;
}) {
  const pct = Math.min(100, Math.max(0, ((value - 0) / (max * 1.3)) * 100));
  const minPct = (min / (max * 1.3)) * 100;
  const maxPct = (max / (max * 1.3)) * 100;
  return (
    <div className="word-bar-row">
      <div className="word-bar-label">
        <span>{label}</span>
        <span className={`word-bar-count ${ok ? "ok" : "warn"}`}>{value} words</span>
      </div>
      <div className="word-bar-track">
        <div className="word-bar-fill" style={{ width: `${pct}%`, background: ok ? "#4F46E5" : "#F59E0B" }} />
        <div className="word-bar-min" style={{ left: `${minPct}%` }} title={`Min: ${min}`} />
        <div className="word-bar-max" style={{ left: `${maxPct}%` }} title={`Max: ${max}`} />
      </div>
      <span className={`word-bar-status ${ok ? "ok" : "warn"}`}>{ok ? "✓" : "!"}</span>
    </div>
  );
}

function renderCaseStudy(text: string): React.ReactNode {
  const UNVERIFIED_RE = /\[UNVERIFIED:\s*([^\]]+)\]/g;
  if (!text) return null;
  const lines = text.split("\n");
  return lines.map((line, i) => {
    if (line.startsWith("### ")) return <h3 key={i} className="ref-section-title">{line.replace(/^###\s*/,"")}</h3>;
    if (line.startsWith("## "))  return <h2 key={i} className="ref-section-title">{line.replace(/^##\s*/,"")}</h2>;
    if (line.startsWith("- ") || line.startsWith("* ")) {
      const parts = splitUnverified(line.replace(/^[-*]\s*/,""), UNVERIFIED_RE);
      return <p key={i} className="ref-list-item">• {parts}</p>;
    }
    if (/^\d+\.\s/.test(line)) {
      const parts = splitUnverified(line, UNVERIFIED_RE);
      return <p key={i} className="ref-list-item">{parts}</p>;
    }
    if (!line.trim()) return <br key={i} />;
    const parts = splitUnverified(line, UNVERIFIED_RE);
    return <p key={i} className="ref-paragraph">{parts}</p>;
  });
}

function splitUnverified(text: string, re: RegExp): React.ReactNode[] {
  const result: React.ReactNode[] = [];
  let last = 0;
  re.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) result.push(text.slice(last, m.index));
    result.push(<span key={m.index} className="unverified-claim" title={m[1]}>[UNVERIFIED: {m[1]}]</span>);
    last = m.index + m[0].length;
  }
  if (last < text.length) result.push(text.slice(last));
  return result;
}

function BetaRefTab({ result, loading, error, onRun }: {
  result: BetaRefResult | null;
  loading: boolean;
  error: string | null;
  onRun: () => void;
}) {
  if (loading) {
    return (
      <div className="beta-loading">
        <Loader2 size={28} className="spin" />
        <p>Generating REF 2029 impact case study…</p>
        <span>Writer agent crafting narrative · Auditor agent checking claims</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="eval-error">
        <AlertTriangle size={18} />
        Beta REF failed: {error}
      </div>
    );
  }
  if (!result) {
    return (
      <div className="eval-empty">
        <Sparkles size={28} />
        <p>Click "Beta REF" to generate a full REF 2029 impact case study with audit flags.</p>
      </div>
    );
  }

  const wc = result.word_counts;
  const criticals = result.flags.filter(f => f.severity === "critical").length;
  const warnings  = result.flags.filter(f => f.severity === "warning").length;

  return (
    <div className="beta-ref-tab">
      <div className="beta-header">
        <div>
          <span className="beta-badge">Beta REF 2029</span>
          <h3>Impact Case Study</h3>
          <p>AI-generated draft · subject to author review before submission</p>
        </div>
        <button
          className="btn-beta"
          onClick={() => result.case_study && downloadReport(result.case_study, "REF_2029_Beta_Case_Study.doc")}
        >
          <Download size={14} /> Export .doc
        </button>
      </div>

      <div className="word-counts-panel">
        <p className="wc-title">Word count compliance</p>
        <WordBar label="Total"               value={wc.total}    min={1800} max={2600} ok={wc.total_ok} />
        <WordBar label="Summary (§1)"        value={wc.summary}  min={80}   max={180}  ok={wc.summary_ok} />
        <WordBar label="Underpinning (§2)"   value={wc.research} min={150}  max={380}  ok={wc.research_ok} />
        <WordBar label="Details of Impact (§4)" value={wc.impact} min={600} max={950}  ok={wc.impact_ok} />
      </div>

      {result.flags.length > 0 && (
        <div className="flags-panel">
          <div className="flags-header">
            <AlertTriangle size={15} />
            <span>Auditor flags</span>
            {criticals > 0 && <span className="flag-count critical">{criticals} critical</span>}
            {warnings > 0  && <span className="flag-count warning">{warnings} warning</span>}
          </div>
          {result.flags.map((flag, i) => (
            <div key={i} className={`flag-item ${flag.severity}`}>
              <div className="flag-meta">
                <span className="flag-section">{flag.section}</span>
                <span className={`flag-sev ${flag.severity}`}>{flag.severity}</span>
              </div>
              <p className="flag-claim">"{flag.claim}"</p>
              <p className="flag-reason">{flag.reason}</p>
            </div>
          ))}
        </div>
      )}

      {result.error && (
        <div className="eval-error">
          <AlertTriangle size={15} /> {result.error}
        </div>
      )}

      <div className="case-study-body">
        {renderCaseStudy(result.case_study)}
      </div>
    </div>
  );
}

function CandidatePicker({ candidates, onPick }: {
  candidates: SearchCandidate[];
  onPick: (doi: string | null, title: string) => void;
}) {
  return (
    <div className="candidate-picker">
      <p className="picker-header">Multiple papers found — select one:</p>
      {candidates.map((c, i) => (
        <button key={i} className="candidate-row" onClick={() => onPick(c.doi, c.title)}>
          <div className="candidate-info">
            <span className="candidate-title">{c.title}</span>
            <span className="candidate-meta">
              {formatAuthors(c.authors)} {c.year ? `· ${c.year}` : ""} {c.venue ? `· ${c.venue}` : ""}
              {c.doi ? <> · <code>{c.doi}</code></> : null}
            </span>
          </div>
          <ArrowRight size={15} className="candidate-arrow" />
        </button>
      ))}
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

type ActiveTab = "overview" | "evidence" | "ref" | "logs" | "eval" | "betaref";

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [query, setQuery]             = useState(SAMPLE_QUERIES[0]);
  const [result, setResult]           = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [activeTab, setActiveTab]     = useState<ActiveTab>("overview");
  const [evidenceFilter, setEvidenceFilter] = useState("all");
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    "Research Influence": true,
    "Applications": true,
    "Technical Adoption": true,
    "Access & Funding": true,
  });
  const [stats, setStats]             = useState<SiteStats | null>(null);
  const [history, setHistory]         = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem("searchHistory") ?? "[]"); } catch { return []; }
  });
  const [evalResult, setEvalResult]   = useState<EvalComparison | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError]     = useState<string | null>(null);
  const [candidates, setCandidates]   = useState<SearchCandidate[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [betaRef, setBetaRef]         = useState<BetaRefResult | null>(null);
  const [betaLoading, setBetaLoading] = useState(false);
  const [betaError, setBetaError]     = useState<string | null>(null);

  // Load stats
  useEffect(() => {
    fetch(`${API_URL}/api/stats`).then(r => r.json()).then(setStats).catch(() => {});
  }, []);

  // Load user history from backend if logged in
  useEffect(() => {
    if (!user) return;
    user.getToken().then(token => {
      fetch(`${API_URL}/api/history`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data?.queries) setHistory(data.queries.slice(0, 10)); })
        .catch(() => {});
    });
  }, [user]);

  // Document title
  useEffect(() => {
    document.title = result?.metadata?.title
      ? `${result.metadata.title} — Veritrace`
      : "Veritrace — Research Impact Analyser";
  }, [result]);

  function updateHistory(q: string) {
    const next = [q, ...history.filter(h => h !== q)].slice(0, 10);
    setHistory(next);
    localStorage.setItem("searchHistory", JSON.stringify(next));
  }

  async function getAuthHeader(): Promise<Record<string, string>> {
    if (!user) return {};
    try { return { Authorization: `Bearer ${await user.getToken()}` }; } catch { return {}; }
  }

  async function runAnalyze(resolvedQuery: string) {
    const cacheKey = `vt_cache_${resolvedQuery}`;
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      try {
        const data = JSON.parse(cached) as AnalyzeResponse;
        setResult(data); setActiveTab("overview");
        updateHistory(resolvedQuery);
        // auto-eval in background
        runEval(resolvedQuery, true);
        return;
      } catch {}
    }

    setLoading(true); setError(null); setResult(null);
    setBetaRef(null); setBetaError(null); setEvalResult(null); setEvalError(null);

    try {
      const headers = { "Content-Type": "application/json", ...(await getAuthHeader()) };
      const resp = await fetch(`${API_URL}/api/analyze`, {
        method: "POST", headers, body: JSON.stringify({ query: resolvedQuery }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? `API ${resp.status}`);
      }
      const data = await resp.json() as AnalyzeResponse;
      setResult(data); setActiveTab("overview");
      localStorage.setItem(cacheKey, JSON.stringify(data));
      updateHistory(resolvedQuery);
      // auto-eval in background
      runEval(resolvedQuery, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function analyze(event?: FormEvent, q?: string) {
    event?.preventDefault();
    const searchQuery = (q ?? query).trim();
    if (!searchQuery) return;
    setQuery(searchQuery);
    setCandidates([]);

    // Detect if DOI / arXiv → go direct
    const isDirectId = /^10\.\d{4,9}\//.test(searchQuery) || /^\d{4}\.\d{4,5}/.test(searchQuery);
    if (isDirectId) { await runAnalyze(searchQuery); return; }

    // Title → search first
    setSearchLoading(true);
    try {
      const resp = await fetch(`${API_URL}/api/search?q=${encodeURIComponent(searchQuery)}`);
      const data = await resp.json();
      const cands: SearchCandidate[] = data.candidates ?? [];
      if (cands.length === 1) {
        const c = cands[0];
        await runAnalyze(c.doi ?? c.title);
      } else if (cands.length > 1) {
        setCandidates(cands);
      } else {
        await runAnalyze(searchQuery);
      }
    } catch {
      await runAnalyze(searchQuery);
    } finally {
      setSearchLoading(false);
    }
  }

  async function runEval(forceQuery?: string, autoMode = false) {
    const q = forceQuery ?? query;
    if (!q) return;
    setEvalLoading(true); setEvalError(null);
    if (!autoMode) setActiveTab("eval");
    try {
      const headers = { "Content-Type": "application/json", ...(await getAuthHeader()) };
      const resp = await fetch(`${API_URL}/api/evaluate`, {
        method: "POST", headers, body: JSON.stringify({ query: q }),
      });
      if (!resp.ok) throw new Error(`Eval API ${resp.status}`);
      const data = await resp.json() as EvalComparison;
      setEvalResult(data);
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setEvalLoading(false);
    }
  }

  async function runBetaRef() {
    if (!result) return;
    setBetaLoading(true); setBetaError(null); setBetaRef(null); setActiveTab("betaref");
    try {
      const headers = { "Content-Type": "application/json", ...(await getAuthHeader()) };
      const body = {
        query: result.metadata.title ?? query,
        title: result.metadata.title,
        authors: result.metadata.authors ?? [],
        year: result.metadata.year,
        doi: result.metadata.doi,
        citation_count: result.citation_count ?? 0,
        summary: result.summary ?? "",
        evidence: (result.evidence ?? []).map(e => ({
          title: e.title, snippet: e.snippet, kind: e.kind,
          source: e.source, url: e.url, year: e.year, authors: e.authors,
        })),
      };
      const resp = await fetch(`${API_URL}/api/ref/beta`, {
        method: "POST", headers, body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(typeof err.detail === "string" ? err.detail : `API ${resp.status}`);
      }
      const data = await resp.json() as BetaRefResult;
      setBetaRef(data);
    } catch (e) {
      setBetaError(e instanceof Error ? e.message : "Beta REF failed");
    } finally {
      setBetaLoading(false);
    }
  }

  async function handleLogout() {
    await logout();
    localStorage.removeItem("isAuthenticated");
    navigate("/");
  }

  function handleExportCSV() {
    window.open(`${API_URL}/api/dataset?fmt=csv`, "_blank");
  }

  const hasResult = !!(result || evalResult || evalLoading || betaLoading || betaRef);
  const showStatuses = loading
    ? withActiveStatuses(INITIAL_STATUSES)
    : (result?.agent_statuses ?? INITIAL_STATUSES);

  return (
    <main className="app-shell">
      {/* ── Sidebar ────────────────────────────────────────── */}
      <aside className="sidebar" aria-label="Workspace navigation">
        <Logo />

        <div className="sidebar-section">
          <div className="sidebar-section-header">
            <Clock size={13} />
            <div className="eyebrow">Recent queries</div>
          </div>
          <div className="sidebar-history-list">
            {(history.length ? history : SAMPLE_QUERIES).map(item => (
              <button key={item} className="sidebar-history-item" onClick={() => analyze(undefined, item)}>
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="sidebar-section">
          <div className="eyebrow" style={{ marginBottom: 8 }}>Data sources</div>
          <div className="sidebar-tags-row">
            {DATA_SOURCES.map(s => (
              <span key={s} className="tag tag-neutral">{s}</span>
            ))}
          </div>
        </div>

        {stats && (
          <div className="sidebar-section">
            <div className="eyebrow" style={{ marginBottom: 10 }}>Pipeline stats</div>
            <div className="sidebar-stat">
              <span className="sidebar-stat-label">Analyses run</span>
              <span className="sidebar-stat-value">{stats.total_analyses}</span>
            </div>
            <div className="sidebar-stat" style={{ marginTop: 6 }}>
              <span className="sidebar-stat-label">Avg. faithfulness</span>
              <span className="sidebar-stat-value">{stats.avg_faithfulness.toFixed(2)}</span>
            </div>
          </div>
        )}

        <button className="sidebar-export" onClick={handleExportCSV}>
          <Download size={13} /> Export dataset CSV
        </button>

        <div className="sidebar-audit-note">
          <span style={{ color: "var(--accent)", marginTop: 1 }}><ShieldCheck size={15} /></span>
          <p>Every agent step and API call is logged. Open the debug logs tab for full auditability.</p>
        </div>

        <div className="sidebar-user" style={{ marginTop: "auto" }}>
          <div className="sidebar-avatar">
            {user?.photoURL
              ? <img src={user.photoURL} alt="" style={{ width: "100%", height: "100%", borderRadius: "50%" }} />
              : (user?.displayName ?? user?.email ?? "D")[0].toUpperCase()
            }
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="sidebar-user-name">{user?.displayName ?? "Researcher"}</div>
            <div className="sidebar-user-email">{user?.email ?? "Demo mode"}</div>
          </div>
          <button className="sidebar-logout" onClick={handleLogout} title="Sign out">
            <LogOut size={15} />
          </button>
        </div>
      </aside>

      {/* ── Workspace ──────────────────────────────────────── */}
      <section className="workspace">
        {/* Topbar */}
        <header className="topbar">
          <div className="topbar-left">
            <div className="eyebrow">Researcher workspace</div>
            <h1 className="topbar-title">Research impact summariser</h1>
          </div>
          <div className="topbar-right">
            <div className="live-indicator">
              <span className="live-dot" />
              Connected to live APIs
            </div>
            <a
              href="https://github.com/sohamdharne/AI_Research_Impact-summariser"
              target="_blank" rel="noreferrer"
              className="btn btn-secondary"
              style={{ fontSize: 13, padding: "7px 12px" }}
            >
              <BookOpen size={13} /> Documentation
            </a>
          </div>
        </header>

        {/* Query panel */}
        <form className="query-panel" onSubmit={analyze}>
          <div className="query-input-row">
            <div className="query-input-wrap">
              <Search size={16} style={{ color: "var(--fg-3)", flexShrink: 0 }} />
              <input
                id="query-input"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Paper DOI, title, arXiv ID, or BibTeX entry"
              />
            </div>
            <div className="query-actions">
              <button type="submit" className="btn btn-primary" disabled={loading || searchLoading}>
                {loading || searchLoading
                  ? <><Loader2 size={14} className="spin" /> Analysing…</>
                  : <><Search size={14} /> Analyse</>
                }
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={evalLoading || loading}
                onClick={() => runEval(undefined, false)}
                title="Force a fresh agentic vs. baseline evaluation"
              >
                {evalLoading ? <Loader2 size={14} className="spin" /> : <BrainCircuit size={14} />}
                {evalResult ? "Re-evaluate" : "Run Evaluation"}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ background: "var(--indigo-800)", borderColor: "var(--indigo-800)" }}
                disabled={!result || betaLoading}
                onClick={runBetaRef}
                title="Generate REF 2029 Beta case study"
              >
                {betaLoading ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
                Beta REF
              </button>
            </div>
          </div>
          <div className="quick-pills">
            {SAMPLE_QUERIES.map(s => (
              <button type="button" key={s} className="quick-pill" onClick={() => analyze(undefined, s)}>
                {s}
              </button>
            ))}
          </div>
        </form>

        {/* Tab nav */}
        {hasResult && (
          <nav className="tabs-bar" aria-label="Result tabs">
            <button className={`tab-btn ${activeTab === "overview" ? "active" : ""}`} onClick={() => setActiveTab("overview")}>
              Overview
            </button>
            {result && (
              <button className={`tab-btn ${activeTab === "evidence" ? "active" : ""}`} onClick={() => setActiveTab("evidence")}>
                Evidence
                <span className={`tab-count ${activeTab === "evidence" ? "active-count" : ""}`}>{result.evidence.length}</span>
              </button>
            )}
            {result?.ref_report && (
              <button className={`tab-btn ${activeTab === "ref" ? "active" : ""}`} onClick={() => setActiveTab("ref")}>
                REF report
              </button>
            )}
            {result && (
              <button className={`tab-btn ${activeTab === "logs" ? "active" : ""}`} onClick={() => setActiveTab("logs")}>
                Debug logs
                <span className={`tab-count ${activeTab === "logs" ? "active-count" : ""}`}>{result.logs.length}</span>
              </button>
            )}
            <button className={`tab-btn ${activeTab === "eval" ? "active" : ""}`} onClick={() => setActiveTab("eval")}>
              Evaluation
              {evalLoading
                ? <Loader2 size={11} className="spin" style={{ marginLeft: 4 }} />
                : evalResult
                  ? <span className="tab-count active-count">vs</span>
                  : null}
            </button>
            <button className={`tab-btn ${activeTab === "betaref" ? "active" : ""}`} onClick={() => setActiveTab("betaref")}>
              Beta REF
              {betaRef && !betaError
                ? <span className="tab-count active-count">✓</span>
                : betaLoading
                  ? <Loader2 size={11} className="spin" style={{ marginLeft: 4 }} />
                  : null}
            </button>
          </nav>
        )}

        {/* Search resolving indicator */}
        {searchLoading && (
          <div style={{ padding: "12px 40px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--fg-2)", borderBottom: "1px solid var(--rule)", background: "var(--linen)" }}>
            <Loader2 size={13} className="spin" />
            Searching CrossRef for paper…
          </div>
        )}

        {/* Candidate picker */}
        {candidates.length > 0 && (
          <div className="candidate-picker-overlay" onClick={e => e.target === e.currentTarget && setCandidates([])}>
            <div className="candidate-picker-sheet">
              <div className="candidate-picker-title">Multiple papers found — select one to analyse</div>
              {candidates.map((c, i) => (
                <div key={i} className="candidate-item" onClick={() => { setCandidates([]); runAnalyze(c.doi ?? c.title); }}>
                  <div className="candidate-title">{c.title}</div>
                  <div className="candidate-authors">{formatAuthors(c.authors)}{c.year ? ` · ${c.year}` : ""}{c.venue ? ` · ${c.venue}` : ""}</div>
                  {c.doi && <div className="candidate-doi">{c.doi}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div style={{ margin: "16px 40px", padding: "12px 16px", background: "var(--rust-100)", color: "var(--rust)", borderRadius: "var(--r-sm)", display: "flex", alignItems: "center", gap: 10, fontSize: 14 }} role="alert">
            <AlertTriangle size={15} />
            {error}
          </div>
        )}

        {/* Tab content */}
        <div className="tab-content">
          {!hasResult && !loading && (
            <div className="empty-state">
              <BookOpen size={40} className="empty-icon" />
              <div className="empty-title">Paste a DOI to begin</div>
              <div className="empty-body">The agent will retrieve metadata, citations, code, patents, and funding signals, then synthesise an auditable 200-word impact summary.</div>
            </div>
          )}

          {loading && !result && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24, padding: "48px 40px" }}>
              <Loader2 size={28} className="spin" style={{ color: "var(--accent)" }} />
              <div style={{ fontSize: 15, fontWeight: 500, color: "var(--fg-1)" }}>Running 9-agent pipeline…</div>
              <div style={{ maxWidth: 380, width: "100%" }}>
                <AgentLogPanel statuses={showStatuses} />
              </div>
            </div>
          )}

          {result && activeTab === "overview" && (
            <OverviewTab
              result={result}
              loading={loading}
              openSections={openSections}
              setOpenSections={setOpenSections}
            />
          )}

          {result && activeTab === "evidence" && (
            <EvidenceTab
              evidence={result.evidence}
              filter={evidenceFilter}
              setFilter={setEvidenceFilter}
            />
          )}

          {result && activeTab === "ref" && result.ref_report && (
            <RefReportTab refReport={result.ref_report} doi={result.metadata.doi} />
          )}

          {result && activeTab === "logs" && (
            <DebugLogsTab logs={result.logs} />
          )}

          {activeTab === "eval" && (
            <EvalTab result={evalResult} loading={evalLoading} error={evalError} />
          )}

          {activeTab === "betaref" && (
            <BetaRefTab
              result={betaRef}
              loading={betaLoading}
              error={betaError}
              onRun={runBetaRef}
            />
          )}
        </div>
      </section>
    </main>
  );
}
