import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setLinkedinUser } = useAuth();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    if (!code) { navigate("/"); return; }
    const isOrcid = state === "orcid";
    const endpoint = isOrcid ? "/api/auth/orcid/exchange" : "/api/auth/linkedin/exchange";
    fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, redirect_uri: `${window.location.origin}/auth/callback` }),
    }).then(r => r.json()).then(data => {
      if (data.token) {
        const provider = isOrcid ? "orcid" : "linkedin";
        const tokenKey = isOrcid ? "orcid_token" : "li_token";
        const userKey = isOrcid ? "orcid_user" : "li_user";
        const u = { uid: data.uid, email: data.email, displayName: data.name, photoURL: null, orcid: data.orcid ?? null };
        sessionStorage.setItem(tokenKey, data.token);
        sessionStorage.setItem(userKey, JSON.stringify(u));
        setLinkedinUser({ ...u, provider, getToken: async () => data.token });
      }
      navigate("/dashboard");
    }).catch(() => navigate("/"));
  }, []);

  return <div style={{display:"flex",alignItems:"center",justifyContent:"center",height:"100vh",fontSize:16}}>Completing sign-in…</div>;
}
