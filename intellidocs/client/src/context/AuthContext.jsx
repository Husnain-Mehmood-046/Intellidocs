/**
 * AuthContext (Day 14).
 *
 * Provides authentication state and methods to the entire React app.
 * Stores JWT in memory + localStorage for persistence across page reloads.
 * Attaches Authorization header to all API calls.
 */
import { createContext, useContext, useState, useEffect, useCallback } from "react";

const AuthContext = createContext(null);

const API_BASE = "/api";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Initialize auth state from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem("intellidocs_token");
    const storedUser = localStorage.getItem("intellidocs_user");

    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  // Helper to make authenticated API calls
  const apiCall = useCallback(
    async (endpoint, options = {}) => {
      const headers = {
        "Content-Type": "application/json",
        ...options.headers,
      };

      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
      });

      if (res.status === 401) {
        // Token expired or invalid - logout
        logout();
        throw new Error("Session expired. Please log in again.");
      }

      return res;
    },
    [token]
  );

  const login = useCallback(
    async (email, password) => {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Login failed");
      }

      setToken(data.token);
      setUser(data.user);
      localStorage.setItem("intellidocs_token", data.token);
      localStorage.setItem("intellidocs_user", JSON.stringify(data.user));

      return data;
    },
    []
  );

  const register = useCallback(
    async (email, password) => {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Registration failed");
      }

      setToken(data.token);
      setUser(data.user);
      localStorage.setItem("intellidocs_token", data.token);
      localStorage.setItem("intellidocs_user", JSON.stringify(data.user));

      return data;
    },
    []
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("intellidocs_token");
    localStorage.removeItem("intellidocs_user");
  }, []);

  const value = {
    user,
    token,
    loading,
    login,
    register,
    logout,
    apiCall,
    isAuthenticated: !!token,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}