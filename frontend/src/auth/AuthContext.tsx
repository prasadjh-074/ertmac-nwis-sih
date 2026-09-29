import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { clearDemoRole, persistDemoRole, readDemoRole } from "./authService";
import type { Role } from "./permissions";

export interface AuthUser {
  id: string;
  name: string;
  initials: string;
  role: Role;
}

interface AuthContextValue {
  user: AuthUser | null;
  loginAs: (role: Role) => void;
  switchRole: (role: Role) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const userForRole = (role: Role): AuthUser =>
  role === "DRILLING_ENGINEER"
    ? { id: "demo-engineer", name: "Demo Engineer", initials: "DE", role }
    : { id: "demo-admin", name: "Demo Administrator", initials: "DA", role };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const role = readDemoRole();
    return role ? userForRole(role) : null;
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loginAs: (role) => {
        persistDemoRole(role);
        setUser(userForRole(role));
      },
      switchRole: (role) => {
        persistDemoRole(role);
        setUser(userForRole(role));
      },
      logout: () => {
        clearDemoRole();
        setUser(null);
      },
    }),
    [user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}