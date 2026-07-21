"use client";

import { useState } from "react";
import { X, Lock, Mail, User as UserIcon } from "lucide-react";
import { toast } from "sonner";

export default function AuthModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: (token: string, user: any) => void;
}) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const endpoint = isLogin ? "/api/auth/login" : "/api/auth/register";
    const payload = isLogin
      ? { email, password }
      : { email, username, password, display_name: displayName || null };

    try {
      const res = await fetch(`http://localhost:8000${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Authentication failed");
      }

      const data = await res.json();
      onSuccess(data.access_token, data.user);
      toast.success(isLogin ? "Logged in successfully" : "Account registered successfully");
      onClose();
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
          <div>
            <h2>{isLogin ? "Welcome Back" : "Create Account"}</h2>
            <p>{isLogin ? "Login to access your conversations" : "Sign up to begin starting workspace chats"}</p>
          </div>
          <button className="icon-btn sm" onClick={onClose} title="Close">
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="form-error" style={{ marginBottom: "16px", padding: "8px", background: "var(--danger-soft)", borderRadius: "var(--radius-sm)" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Email Address</label>
            <div style={{ position: "relative" }}>
              <Mail size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
              <input
                type="email"
                required
                className="form-input"
                style={{ paddingLeft: "36px" }}
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          {!isLogin && (
            <>
              <div className="form-group">
                <label className="form-label">Username</label>
                <div style={{ position: "relative" }}>
                  <UserIcon size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                  <input
                    type="text"
                    required
                    className="form-input"
                    style={{ paddingLeft: "36px" }}
                    placeholder="johndoe"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Display Name (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="John Doe"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>
            </>
          )}

          <div className="form-group">
            <label className="form-label">Password</label>
            <div style={{ position: "relative" }}>
              <Lock size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
              <input
                type="password"
                required
                className="form-input"
                style={{ paddingLeft: "36px" }}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <button type="submit" disabled={loading} className="btn btn-primary" style={{ marginTop: "8px" }}>
            {loading ? "Please wait..." : isLogin ? "Sign In" : "Sign Up"}
          </button>
        </form>

        <div style={{ marginTop: "20px", textAlign: "center", fontSize: "13px", color: "var(--text-secondary)" }}>
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button
            className="btn-ghost"
            style={{ fontWeight: 600, border: "none", background: "none", cursor: "pointer", padding: 0 }}
            onClick={() => setIsLogin(!isLogin)}
          >
            {isLogin ? "Sign Up" : "Sign In"}
          </button>
        </div>
      </div>
    </div>
  );
}
