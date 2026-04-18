"use client";

import { createContext, ReactNode, startTransition, useContext, useEffect, useMemo, useState } from "react";

import { apiRequest } from "@/lib/api";
import { clearStorage, readStorage, writeStorage } from "@/lib/storage";
import { AuthData, User } from "@/lib/types";

type SessionState = {
  token: string | null;
  user: User | null;
};

type AuthContextValue = {
  ready: boolean;
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
};

const SESSION_KEY = "prep-session";
const LEGACY_SESSION_KEY = "perp-session";
const AuthContext = createContext<AuthContextValue | null>(null);

function persistSession(data: AuthData) {
  const session: SessionState = {
    token: data.access_token,
    user: data.user,
  };
  writeStorage(SESSION_KEY, session);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const saved =
      readStorage<SessionState>(SESSION_KEY) ??
      readStorage<SessionState>(LEGACY_SESSION_KEY);
  
    if (saved?.token) {
      setToken(saved.token);
      setUser(saved.user);
    }
  
    setReady(true);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      token,
      user,
      login: async (email: string, password: string) => {
        const result = await apiRequest<AuthData>("/auth/login", {
          method: "POST",
          body: { email, password },
        });
        startTransition(() => {
          persistSession(result);
          setToken(result.access_token);
          setUser(result.user);
        });
      },
      signup: async (name: string, email: string, password: string) => {
        const result = await apiRequest<AuthData>("/auth/signup", {
          method: "POST",
          body: { name, email, password },
        });
        startTransition(() => {
          persistSession(result);
          setToken(result.access_token);
          setUser(result.user);
        });
      },
      logout: () => {
        clearStorage(SESSION_KEY);
        clearStorage(LEGACY_SESSION_KEY);
        setToken(null);
        setUser(null);
      },
    }),
    [ready, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
