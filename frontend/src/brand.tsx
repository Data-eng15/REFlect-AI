import React from "react";

/* ── REFlect AI wordmark ──────────────────────────────────────────────────
   Evidence-dot motif from the REFlect AI design system: a serif italic "R"
   paired with an indigo bullet standing in for a "verified evidence" dot,
   followed by the REFlect AI wordmark. */
export function Logo({ size = 28, showWord = true }: { size?: number; showWord?: boolean }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 10, lineHeight: 1 }}>
      <span
        style={{
          fontFamily: "var(--font-serif)", fontStyle: "italic", fontWeight: 600,
          fontSize: size, letterSpacing: "-0.03em", color: "var(--ink)",
          display: "inline-flex", alignItems: "baseline", gap: 1,
        }}
      >
        R
        <span
          style={{
            display: "inline-block", width: Math.max(3.5, size / 8), height: Math.max(3.5, size / 8),
            background: "var(--accent)", borderRadius: "50%", alignSelf: "center",
          }}
        />
      </span>
      {showWord && (
        <span
          style={{
            fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: size * 0.56,
            color: "var(--ink)", letterSpacing: "-0.01em", whiteSpace: "nowrap",
          }}
        >
          REFlect<span style={{ color: "var(--accent)" }}> AI</span>
        </span>
      )}
    </div>
  );
}

export const ORCID_GREEN = "#A6CE39";

/* Official ORCID iD mark. */
export function OrcidMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 256 256" aria-hidden="true">
      <circle cx="128" cy="128" r="128" fill={ORCID_GREEN} />
      <g fill="#fff">
        <rect x="86" y="79" width="14" height="105" rx="2" />
        <circle cx="93" cy="60" r="9" />
        <path d="M124 79h38c30 0 49 22 49 52 0 31-21 53-50 53h-37V79zm14 13v79h22c25 0 36-17 36-40 0-24-13-39-36-39h-22z" />
      </g>
    </svg>
  );
}

export function Eyebrow({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        fontSize: 11, lineHeight: "16px", fontWeight: 600, letterSpacing: "0.12em",
        textTransform: "uppercase", color: "var(--fg-2)", ...style,
      }}
    >
      {children}
    </div>
  );
}
