import { useState, useEffect } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./components/Login";
import Register from "./components/Register";
import ChatWindow from "./components/ChatWindow";
import AdminDashboard from "./pages/AdminDashboard";
import "./index.css";

/**
 * Shell component with persistent header navigation.
 * Provides consistent app chrome across all authenticated routes.
 * Responsive: collapses nav to hamburger menu on mobile.
 */
function Shell({ children, user, onLogout }) {
  const [activeRoute, setActiveRoute] = useState(window.location.pathname);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleRouteChange = () => {
      setActiveRoute(window.location.pathname);
      setMobileMenuOpen(false);
    };
    window.addEventListener("popstate", handleRouteChange);
    return () => window.removeEventListener("popstate", handleRouteChange);
  }, []);

  const navigate = (path) => {
    window.history.pushState({}, "", path);
    setActiveRoute(path);
    window.dispatchEvent(new Event("popstate"));
  };

  const isAuthRoute = activeRoute === "/login" || activeRoute === "/register";

  if (isAuthRoute) {
    return children; // Auth pages don't need the shell
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          height: "var(--header-height)",
          background: "var(--paper-elevated)",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 var(--content-padding)",
          zIndex: 100,
          boxShadow: "var(--shadow-sm)",
        }}
        role="banner"
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          <a
            href="/"
            onClick={(e) => { e.preventDefault(); navigate("/"); }}
            style={{
              fontSize: "var(--text-xl)",
              fontWeight: "var(--font-semibold)",
              color: "var(--ink)",
              textDecoration: "none",
              letterSpacing: "-0.02em",
            }}
            aria-label="IntelliDocs home"
          >
            IntelliDocs
          </a>
          
          {/* Desktop nav */}
          <nav style={{ display: "none", gap: "var(--space-2)", marginLeft: "var(--space-4)" }} aria-label="Main navigation" className="desktop-nav">
            <button
              onClick={() => navigate("/")}
              style={{
                padding: "var(--space-2) var(--space-4)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--font-medium)",
                fontFamily: "var(--font-sans)",
                color: activeRoute === "/" ? "var(--accent)" : "var(--ink-muted)",
                background: activeRoute === "/" ? "var(--accent-subtle)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
                transition: "color var(--transition-fast), background var(--transition-fast)",
              }}
              aria-current={activeRoute === "/" ? "page" : undefined}
            >
              Chat
            </button>
            <button
              onClick={() => navigate("/admin")}
              style={{
                padding: "var(--space-2) var(--space-4)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--font-medium)",
                fontFamily: "var(--font-sans)",
                color: activeRoute === "/admin" ? "var(--accent)" : "var(--ink-muted)",
                background: activeRoute === "/admin" ? "var(--accent-subtle)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
                transition: "color var(--transition-fast), background var(--transition-fast)",
              }}
              aria-current={activeRoute === "/admin" ? "page" : undefined}
            >
              Admin
            </button>
          </nav>

          {/* Mobile menu button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-nav"
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "40px",
              height: "40px",
              padding: 0,
              background: "transparent",
              border: "none",
              borderRadius: "var(--radius-md)",
              cursor: "pointer",
              color: "var(--ink)",
            }}
            className="mobile-menu-toggle"
          >
            {mobileMenuOpen ? (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            ) : (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            )}
          </button>
        </div>
        
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          {user && (
            <span style={{ fontSize: "var(--text-sm)", color: "var(--ink-muted)", display: "none" }} className="user-email">
              {user.email}
            </span>
          )}
          <button
            onClick={onLogout}
            style={{
              padding: "var(--space-2) var(--space-4)",
              fontSize: "var(--text-sm)",
              fontWeight: "var(--font-medium)",
              fontFamily: "var(--font-sans)",
              color: "var(--trust-low)",
              background: "var(--trust-low-bg)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              cursor: "pointer",
              transition: "background var(--transition-fast), color var(--transition-fast)",
            }}
          >
            Logout
          </button>
        </div>

        {/* Mobile nav panel */}
        {mobileMenuOpen && (
          <nav
            id="mobile-nav"
            style={{
              position: "absolute",
              top: "var(--header-height)",
              left: 0,
              right: 0,
              background: "var(--paper-elevated)",
              borderBottom: "1px solid var(--border)",
              padding: "var(--space-4) var(--content-padding)",
              boxShadow: "var(--shadow-md)",
              zIndex: 99,
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
            }}
            aria-label="Mobile navigation"
          >
            <button
              onClick={() => navigate("/")}
              style={{
                padding: "var(--space-3) var(--space-4)",
                fontSize: "var(--text-md)",
                fontWeight: "var(--font-medium)",
                fontFamily: "var(--font-sans)",
                color: activeRoute === "/" ? "var(--accent)" : "var(--ink)",
                background: activeRoute === "/" ? "var(--accent-subtle)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
                textAlign: "left",
                transition: "color var(--transition-fast), background var(--transition-fast)",
              }}
              aria-current={activeRoute === "/" ? "page" : undefined}
            >
              Chat
            </button>
            <button
              onClick={() => navigate("/admin")}
              style={{
                padding: "var(--space-3) var(--space-4)",
                fontSize: "var(--text-md)",
                fontWeight: "var(--font-medium)",
                fontFamily: "var(--font-sans)",
                color: activeRoute === "/admin" ? "var(--accent)" : "var(--ink)",
                background: activeRoute === "/admin" ? "var(--accent-subtle)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
                textAlign: "left",
                transition: "color var(--transition-fast), background var(--transition-fast)",
              }}
              aria-current={activeRoute === "/admin" ? "page" : undefined}
            >
              Admin
            </button>
            {user && (
              <div style={{ padding: "var(--space-2) var(--space-4)", fontSize: "var(--text-sm)", color: "var(--ink-muted)", borderTop: "1px solid var(--border)", marginTop: "var(--space-2)" }}>
                {user.email}
              </div>
            )}
          </nav>
        )}
      </header>
      <main
        style={{
          flex: 1,
          paddingTop: "calc(var(--header-height) + var(--space-6))",
          paddingBottom: "var(--space-8)",
          paddingLeft: "var(--content-padding)",
          paddingRight: "var(--content-padding)",
          maxWidth: "var(--content-max)",
          margin: "0 auto",
          width: "100%",
        }}
        role="main"
      >
        {children}
      </main>
    </div>
  );
}

/**
 * Main App component with authentication routing.
 *
 * Routes:
 * - /login    -> Login page
 * - /register -> Register page
 * - /         -> Chat window (protected, redirects to /login if not authenticated)
 * - /admin    -> Admin dashboard (protected, shows evaluation metrics)
 */
function AppContent() {
  const { isAuthenticated, loading, user, logout } = useAuth();
  const [route, setRoute] = useState(window.location.pathname);

  // Listen for route changes (popstate for browser back/forward, and manual pushState)
  useEffect(() => {
    const handleRouteChange = () => setRoute(window.location.pathname);
    window.addEventListener("popstate", handleRouteChange);
    return () => window.removeEventListener("popstate", handleRouteChange);
  }, []);

  // Redirect logic
  useEffect(() => {
    if (!loading) {
      if (route === "/login" || route === "/register") {
        if (isAuthenticated) {
          window.history.pushState({}, "", "/");
          setRoute("/");
        }
      } else if (!isAuthenticated) {
        window.history.pushState({}, "", "/login");
        setRoute("/login");
      }
    }
  }, [isAuthenticated, loading, route]);

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "100vh",
        }}
      >
        <div style={{ fontSize: "var(--text-lg)", color: "var(--ink-muted)" }}>Loading…</div>
      </div>
    );
  }

  // Render based on route
  const renderContent = () => {
    switch (route) {
      case "/login":
        return <Login />;
      case "/register":
        return <Register />;
      case "/admin":
        return <AdminDashboard />;
      default:
        return <ChatWindow />;
    }
  };

  return (
    <Shell user={user} onLogout={logout}>
      {renderContent()}
    </Shell>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}