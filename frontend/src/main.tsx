import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthContext";
import LandingPage from "./LandingPage";
import Dashboard from "./Dashboard";
import AuthCallback from "./AuthCallback";
import "./styles.css";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <div style={{ fontSize: 14, color: "#64748b" }}>Loading…</div>
      </div>
    );
  }
  // Allow access if user is logged in OR if legacy localStorage auth is set (demo mode)
  const legacyAuth = localStorage.getItem("isAuthenticated") === "true";
  if (!user && !legacyAuth) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
