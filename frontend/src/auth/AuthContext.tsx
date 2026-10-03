import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { queryClient } from "@/lib/queryClient";
import { logSessionEvent } from "@/lib/sessionLog";
import { demoSignIn, restoreSession, signOut, type AuthUser } from "./authService";
import { hasPermission, type Permission, type Role } from "./permissions";

interface AuthContextValue {
  user: AuthUser | null;
  loginAs: (role: Role) => void;
  logout: () => void;
  can: (permission: Permission) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => restoreSession());

  const loginAs = useCallback((role: Role) => {
    queryClient.clear();
    const u = demoSignIn(role);
    logSessionEvent(u.employeeId, "Signed in (demo)", role, "Allowed");
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    setUser((u) => {
      if (u) logSessionEvent(u.employeeId, "Signed out", u.role, "Allowed");
      return null;
    });
    signOut();
    queryClient.clear();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loginAs, logout, can: (p) => hasPermission(user?.role, p) }),
    [user, loginAs, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
