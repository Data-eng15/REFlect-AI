import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { useAuth } from "./AuthContext";

export default function LoginModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const { loginWithGoogle, loginWithGithub, loginWithOrcid } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const handleGoogle = async () => {
    setLoading("google"); setError(null);
    try {
      await loginWithGoogle();
      onClose(); navigate("/dashboard");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Google sign-in failed";
      setError(msg.includes("not-configured") || msg.includes("api-key") ? "Google/GitHub sign-in isn't configured yet — use ORCID above." : msg);
    } finally { setLoading(null); }
  };

  const handleGithub = async () => {
    setLoading("github"); setError(null);
    try {
      await loginWithGithub();
      onClose(); navigate("/dashboard");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "GitHub sign-in failed";
      setError(msg.includes("not-configured") || msg.includes("api-key") ? "Google/GitHub sign-in isn't configured yet — use ORCID above." : msg);
    } finally { setLoading(null); }
  };

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

          <button className="social-btn" onClick={handleGoogle} disabled={!!loading}>
            {loading === "google" ? <span className="social-spinner" /> : (
              <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
                <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908C16.616 14.126 17.64 11.85 17.64 9.2z" fill="#4285F4"/>
                <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
                <path d="M3.964 10.706A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.038l3.007-2.332z" fill="#FBBC05"/>
                <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
              </svg>
            )}
            Continue with Google
          </button>

          <button className="social-btn" onClick={handleGithub} disabled={!!loading}>
            {loading === "github" ? <span className="social-spinner" /> : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
              </svg>
            )}
            Continue with GitHub
          </button>

        </div>

        <p className="modal-footnote">
          New researcher?{" "}
          <a href="#" onClick={e => e.preventDefault()}>Request institutional access.</a>
        </p>
      </div>
    </div>
  );
}
