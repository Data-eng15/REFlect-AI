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
    if (!code) { navigate("/"); return; }
    fetch(`${API_URL}/api/auth/linkedin/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, redirect_uri: `${window.location.origin}/auth/callback` }),
    }).then(r => r.json()).then(data => {
      if (data.token) {
        sessionStorage.setItem("li_token", data.token);
        sessionStorage.setItem("li_user", JSON.stringify({ uid: data.uid, email: data.email, displayName: data.name, photoURL: null }));
        setLinkedinUser({ uid: data.uid, email: data.email, displayName: data.name, photoURL: null, provider: "linkedin", getToken: async () => data.token });
      }
      navigate("/dashboard");
    }).catch(() => navigate("/"));
  }, []);

  return <div style={{display:"flex",alignItems:"center",justifyContent:"center",height:"100vh",fontSize:16}}>Completing sign-in…</div>;
}
