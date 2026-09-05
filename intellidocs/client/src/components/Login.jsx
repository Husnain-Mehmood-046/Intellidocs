/**
 * Login component (Redesigned - Pass 2).
 *
 * Clean, accessible auth form with the IntelliDocs visual language.
 * Visible labels, clear focus states, actionable error messages.
 */
import { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setFieldErrors({});

    // Client-side validation
    const errors = {};
    if (!email.trim()) {
      errors.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = "Enter a valid email address";
    }
    if (!password) {
      errors.password = "Password is required";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setLoading(true);

    try {
      await login(email, password);
    } catch (err) {
      const msg = err.message || "Sign in failed";
      if (msg.toLowerCase().includes("email") || msg.toLowerCase().includes("user")) {
        setFieldErrors({ email: "No account found with this email" });
      } else if (msg.toLowerCase().includes("password") || msg.toLowerCase().includes("credential")) {
        setFieldErrors({ password: "Incorrect password" });
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleNavigate = (path) => (e) => {
    e.preventDefault();
    window.history.pushState({}, "", path);
    window.dispatchEvent(new Event("popstate"));
  };

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        background: "var(--paper)",
        padding: "var(--space-6) var(--space-4)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          padding: "var(--space-8)",
          background: "var(--paper-elevated)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-md)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "var(--space-8)" }}>
          <h1 style={{ margin: "0 0 var(--space-2)", fontSize: "var(--text-3xl)", fontWeight: "var(--font-semibold)", color: "var(--ink)", letterSpacing: "-0.02em" }}>
            IntelliDocs
          </h1>
          <p style={{ margin: 0, fontSize: "var(--text-md)", color: "var(--ink-muted)" }}>
            Sign in to continue your research
          </p>
        </div>

        {error && (
          <div
            style={{
              padding: "var(--space-3) var(--space-4)",
              background: "var(--trust-low-bg)",
              color: "var(--trust-low)",
              border: "1px solid var(--trust-low)",
              borderRadius: "var(--radius-md)",
              marginBottom: "var(--space-5)",
              fontSize: "var(--text-sm)",
            }}
            role="alert"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "var(--space-5)" }}>
            <label
              htmlFor="email"
              style={{
                display: "block",
                marginBottom: "var(--space-2)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--font-medium)",
                color: "var(--ink)",
              }}
            >
              Email
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); if (fieldErrors.email) setFieldErrors(prev => ({ ...prev, email: null })); }}
              required
              disabled={loading}
              autoComplete="email"
              aria-invalid={fieldErrors.email ? "true" : "false"}
              aria-describedby={fieldErrors.email ? "email-error" : undefined}
              style={{
                width: "100%",
                padding: "var(--space-3) var(--space-4)",
                fontSize: "var(--text-md)",
                fontFamily: "var(--font-sans)",
                color: "var(--ink)",
                background: "var(--paper-elevated)",
                border: `1px solid ${fieldErrors.email ? "var(--trust-low)" : "var(--border)"}`,
                borderRadius: "var(--radius-md)",
                boxSizing: "border-box",
                transition: "border-color var(--transition-fast), box-shadow var(--transition-fast)",
              }}
            />
            {fieldErrors.email && (
              <p id="email-error" style={{ margin: "var(--space-1) 0 0", fontSize: "var(--text-xs)", color: "var(--trust-low)" }}>
                {fieldErrors.email}
              </p>
            )}
          </div>

          <div style={{ marginBottom: "var(--space-6)" }}>
            <label
              htmlFor="password"
              style={{
                display: "block",
                marginBottom: "var(--space-2)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--font-medium)",
                color: "var(--ink)",
              }}
            >
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); if (fieldErrors.password) setFieldErrors(prev => ({ ...prev, password: null })); }}
              required
              disabled={loading}
              autoComplete="current-password"
              aria-invalid={fieldErrors.password ? "true" : "false"}
              aria-describedby={fieldErrors.password ? "password-error" : undefined}
              style={{
                width: "100%",
                padding: "var(--space-3) var(--space-4)",
                fontSize: "var(--text-md)",
                fontFamily: "var(--font-sans)",
                color: "var(--ink)",
                background: "var(--paper-elevated)",
                border: `1px solid ${fieldErrors.password ? "var(--trust-low)" : "var(--border)"}`,
                borderRadius: "var(--radius-md)",
                boxSizing: "border-box",
                transition: "border-color var(--transition-fast), box-shadow var(--transition-fast)",
              }}
            />
            {fieldErrors.password && (
              <p id="password-error" style={{ margin: "var(--space-1) 0 0", fontSize: "var(--text-xs)", color: "var(--trust-low)" }}>
                {fieldErrors.password}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "var(--space-3) var(--space-5)",
              fontSize: "var(--text-md)",
              fontWeight: "var(--font-semibold)",
              fontFamily: "var(--font-sans)",
              color: "white",
              background: loading ? "var(--border-strong)" : "var(--accent)",
              border: "none",
              borderRadius: "var(--radius-md)",
              cursor: loading ? "not-allowed" : "pointer",
              transition: "background var(--transition-fast)",
            }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <p style={{ textAlign: "center", marginTop: "var(--space-6)", fontSize: "var(--text-sm)", color: "var(--ink-muted)" }}>
          Don't have an account?{" "}
          <a
            href="/register"
            onClick={handleNavigate("/register")}
            style={{ color: "var(--accent)", textDecoration: "none", fontWeight: "var(--font-medium)" }}
          >
            Create one
          </a>
        </p>
      </div>
    </div>
  );
}