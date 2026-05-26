import React, { createContext, useContext, useEffect, useState } from "react";
import { GoogleAuthProvider, GithubAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "firebase/auth";
import { auth } from "./firebase";

type AuthUser = {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  provider: string;
  getToken: () => Promise<string>;
};

type AuthCtx = {
  user: AuthUser | null;
  loading: boolean;
  loginWithGoogle: () => Promise<void>;
  loginWithGithub: () => Promise<void>;
  loginWithLinkedin: () => void;
  logout: () => Promise<void>;
  setLinkedinUser: (u: AuthUser) => void;
};

const Ctx = createContext<AuthCtx>({
  user: null, loading: true,
  loginWithGoogle: async () => {}, loginWithGithub: async () => {},
  loginWithLinkedin: () => {}, logout: async () => {}, setLinkedinUser: () => {},
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
        if (!li) setUser(null);
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

  const logout = async () => {
    if (auth) await signOut(auth);
    sessionStorage.removeItem("li_token");
    sessionStorage.removeItem("li_user");
    sessionStorage.removeItem("demo_access");
    setUser(null);
  };

  const setLinkedinUser = (u: AuthUser) => setUser(u);

  return <Ctx.Provider value={{ user, loading, loginWithGoogle, loginWithGithub, loginWithLinkedin, logout, setLinkedinUser }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
