import React, { createContext, useContext, useEffect, useState } from "react";
import { GoogleAuthProvider, GithubAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "firebase/auth";
import { auth } from "./firebase";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

type AuthUser = {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  provider: string;
  orcid?: string | null;
  getToken: () => Promise<string>;
};

type AuthCtx = {
  user: AuthUser | null;
  loading: boolean;
  loginWithGoogle: () => Promise<void>;
  loginWithGithub: () => Promise<void>;
  loginWithLinkedin: () => void;
  loginWithOrcid: () => Promise<boolean>;
  logout: () => Promise<void>;
  setLinkedinUser: (u: AuthUser) => void;
};

const Ctx = createContext<AuthCtx>({
  user: null, loading: true,
  loginWithGoogle: async () => {}, loginWithGithub: async () => {},
  loginWithLinkedin: () => {}, loginWithOrcid: async () => false, logout: async () => {}, setLinkedinUser: () => {},
});

const FIREBASE_CONFIGURED = auth !== null;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Restore LinkedIn session
    const li_token = sessionStorage.getItem("li_token");
    const li_user = sessionStorage.getItem("li_user");
    if (li_token && li_user) {
      try {
        const u = JSON.parse(li_user);
        setUser({ ...u, provider: "linkedin", getToken: async () => li_token });
      } catch {}
    }
    // Restore ORCID session
    const orcid_token = sessionStorage.getItem("orcid_token");
    const orcid_user = sessionStorage.getItem("orcid_user");
    if (orcid_token && orcid_user) {
      try {
        const u = JSON.parse(orcid_user);
        setUser({ ...u, provider: "orcid", getToken: async () => orcid_token });
      } catch {}
    }
    if (!FIREBASE_CONFIGURED) { setLoading(false); return; }
    return onAuthStateChanged(auth!, (fbUser) => {
      if (fbUser) {
        setUser({
          uid: fbUser.uid, email: fbUser.email, displayName: fbUser.displayName,
          photoURL: fbUser.photoURL, provider: fbUser.providerData[0]?.providerId || "firebase",
          getToken: () => fbUser.getIdToken(),
        });
      } else {
        const li = sessionStorage.getItem("li_token");
        const orc = sessionStorage.getItem("orcid_token");
        if (!li && !orc) setUser(null);
      }
      setLoading(false);
    });
  }, []);

  const loginWithGoogle = async () => {
    if (!auth) return;
    const result = await signInWithPopup(auth, new GoogleAuthProvider());
    const u = result.user;
    setUser({ uid: u.uid, email: u.email, displayName: u.displayName, photoURL: u.photoURL, provider: "google", getToken: () => u.getIdToken() });
  };

  const loginWithGithub = async () => {
    if (!auth) return;
    const result = await signInWithPopup(auth, new GithubAuthProvider());
    const u = result.user;
    setUser({ uid: u.uid, email: u.email, displayName: u.displayName, photoURL: u.photoURL, provider: "github", getToken: () => u.getIdToken() });
  };

  const loginWithLinkedin = () => {
    const clientId = import.meta.env.VITE_LINKEDIN_CLIENT_ID || "";
    const redirect = encodeURIComponent(`${window.location.origin}/auth/callback`);
    window.location.href = `https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=${clientId}&redirect_uri=${redirect}&scope=openid%20profile%20email`;
  };

  // ORCID sign-in. Asks the backend whether real OAuth is configured:
  //  - configured  → redirect to ORCID's authorize page (real 3-legged flow).
  //  - not configured (mock) → exchange a placeholder code so the showcase
  //    still signs in as the sample researcher. Resolves true when signed in
  //    in-place (mock), false when the browser is being redirected (real).
  const loginWithOrcid = async (): Promise<boolean> => {
    let cfg: { configured?: boolean; client_id?: string; authorize_base?: string } = {};
    try {
      cfg = await fetch(`${API_URL}/api/auth/orcid/config`).then((r) => r.json());
    } catch {
      cfg = {};
    }
    const redirectUri = `${window.location.origin}/auth/callback`;
    if (cfg.configured && cfg.client_id) {
      const base = cfg.authorize_base || "https://orcid.org";
      const redirect = encodeURIComponent(redirectUri);
      window.location.href = `${base}/oauth/authorize?client_id=${cfg.client_id}&response_type=code&scope=/authenticate&redirect_uri=${redirect}&state=orcid`;
      return false;
    }
    // Mock flow
    const data = await fetch(`${API_URL}/api/auth/orcid/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "mock", redirect_uri: redirectUri }),
    }).then((r) => r.json());
    if (!data?.token) throw new Error("ORCID sign-in failed");
    const u = { uid: data.uid, email: data.email, displayName: data.name, photoURL: null, orcid: data.orcid };
    sessionStorage.setItem("orcid_token", data.token);
    sessionStorage.setItem("orcid_user", JSON.stringify(u));
    setUser({ ...u, provider: "orcid", getToken: async () => data.token });
    return true;
  };

  const logout = async () => {
    if (auth) await signOut(auth);
    sessionStorage.removeItem("li_token");
    sessionStorage.removeItem("li_user");
    sessionStorage.removeItem("orcid_token");
    sessionStorage.removeItem("orcid_user");
    sessionStorage.removeItem("demo_access");
    setUser(null);
  };

  const setLinkedinUser = (u: AuthUser) => setUser(u);

  return <Ctx.Provider value={{ user, loading, loginWithGoogle, loginWithGithub, loginWithLinkedin, loginWithOrcid, logout, setLinkedinUser }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
