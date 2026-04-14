import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";

interface AuthState {
  isAuthenticated: boolean;
  username: string | null;
  rol: string | null;
  loading: boolean;
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  isSuperAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    username: null,
    rol: null,
    loading: true,
  });

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      axios
        .get("/api/admin/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        })
        .then((res) => {
          setState({
            isAuthenticated: true,
            username: res.data.username,
            rol: res.data.rol,
            loading: false,
          });
        })
        .catch(() => {
          localStorage.clear();
          setState({ isAuthenticated: false, username: null, rol: null, loading: false });
        });
    } else {
      setState({ isAuthenticated: false, username: null, rol: null, loading: false });
    }
  }, []);

  const login = async (username: string, password: string) => {
    const { data } = await axios.post("/api/admin/auth/login", {
      username,
      password,
    });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    // Fetch role from /me after login
    const me = await axios.get("/api/admin/auth/me", {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    setState({
      isAuthenticated: true,
      username,
      rol: me.data.rol,
      loading: false,
    });
  };

  const logout = () => {
    localStorage.clear();
    setState({ isAuthenticated: false, username: null, rol: null, loading: false });
  };

  const isAdmin = state.rol === "admin" || state.rol === "superadmin";
  const isSuperAdmin = state.rol === "superadmin";

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAdmin, isSuperAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
