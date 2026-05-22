import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  role: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  initialized: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token"));
  const [user, setUser] = useState<AuthUser | null>(null);
  const [initialized, setInitialized] = useState(false);

  const isAuthenticated = token !== null && user !== null;

  // 有 token 时恢复用户信息
  useEffect(() => {
    if (!token) {
      setUser(null);
      setInitialized(true);
      return;
    }
    const base = import.meta.env.VITE_GOVDOC_API_BASE_URL || "";
    fetch(`${base}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("token 无效");
        return res.json();
      })
      .then((data) => {
        setUser(data);
        setInitialized(true);
      })
      .catch(() => {
        localStorage.removeItem("token");
        setToken(null);
        setUser(null);
        setInitialized(true);
      });
  }, [token]);

  async function login(username: string, password: string) {
    const base = import.meta.env.VITE_GOVDOC_API_BASE_URL || "";
    const res = await fetch(`${base}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(body || "登录失败");
    }
    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }

  async function register(username: string, password: string, displayName: string) {
    const base = import.meta.env.VITE_GOVDOC_API_BASE_URL || "";
    const res = await fetch(`${base}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, display_name: displayName }),
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(body || "注册失败");
    }
    await login(username, password);
  }

  function logout() {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ token, user, initialized, isAuthenticated, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
