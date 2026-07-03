import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { useAuth } from "./AuthContext";

export default function LoginModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const { loginWithOrcid } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const handleOrcid = async () => {
    setLoading("orcid"); setError(null);
    try {
      const signedIn = await loginWithOrcid();
      // When ORCID OAuth is configured, loginWithOrcid redirects the browser to
      // orcid.org and returns false; on the (mock) in-place path it returns true.
      if (signedIn) { onClose(); navigate("/dashboard"); }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "ORCID sign-in failed");
      setLoading(null);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-sheet">

        <button className="modal-close" onClick={onClose} aria-label="Close">
          <X size={16} />
        </button>

        <div className="modal-header">
          <div className="modal-title">Sign in to REFlect AI</div>
          <div className="modal-subtitle">Continue to your researcher workspace.</div>
        </div>

        {error && <div className="modal-error">{error}</div>}

        {/* Social sign-in */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button className="social-btn" onClick={handleOrcid} disabled={!!loading} style={{ borderColor: "#A6CE39", fontWeight: 600 }}>
            {loading === "orcid" ? <span className="social-spinner" /> : (
              <svg width="16" height="16" viewBox="0 0 256 256" aria-hidden="true">
                <circle cx="128" cy="128" r="128" fill="#A6CE39"/>
                <path fill="#fff" d="M86.3 186.2H70.9V79.1h15.4v107.1zM108.9 79.1h41.6c39.6 0 57 28.3 57 53.6 0 27.5-21.5 53.6-56.8 53.6h-41.8V79.1zm15.4 93.3h24.5c34.9 0 42.9-26.5 42.9-39.7 0-21.5-13.7-39.7-43.7-39.7h-23.7v79.4zM88.7 56.8c0 5.5-4.5 10.1-10.1 10.1-5.6 0-10.1-4.6-10.1-10.1 0-5.6 4.5-10.1 10.1-10.1 5.6 0 10.1 4.6 10.1 10.1z"/>
              </svg>
            )}
            Continue with ORCID iD
          </button>
        </div>

        <div className="modal-divider">Verified researcher sign-in</div>

        <p className="modal-footnote">
          New researcher?{" "}
          <a href="#" onClick={e => e.preventDefault()}>Request institutional access.</a>
        </p>
      </div>
    </div>
  );
}
