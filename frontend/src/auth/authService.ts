import type { Role } from "./permissions";

// TODO(auth): Replace demo authentication with organizational SSO/JWT.
// The UI only depends on AuthUser + Role, so an OIDC/JWT provider can implement
// signIn/restore/signOut without touching any page or component.

export interface AuthUser {
  id: string;
  employeeId: string;
  name: string;
  initials: string;
  department: string;
  role: Role;
  authMode: "demo";
}

const STORAGE_KEY = "nwis-demo-session";
export const DEMO_AUTH_LABEL = "DEMO AUTHENTICATION";

const DEMO_IDENTITIES: Record<Role, AuthUser> = {
  DRILLING_ENGINEER: {
    id: "demo-engineer",
    employeeId: "DEMO-ENG",
    name: "Demo Drilling Engineer",
    initials: "DE",
    department: "Drilling Engineering",
    role: "DRILLING_ENGINEER",
    authMode: "demo",
  },
  SYSTEM_ADMIN: {
    id: "demo-admin",
    employeeId: "DEMO-ADM",
    name: "Demo System Administrator",
    initials: "SA",
    department: "IT Platform",
    role: "SYSTEM_ADMIN",
    authMode: "demo",
  },
};

export const demoIdentities = (): AuthUser[] => Object.values(DEMO_IDENTITIES);

export function demoSignIn(role: Role): AuthUser {
  const user = DEMO_IDENTITIES[role];
  window.localStorage.setItem(STORAGE_KEY, role);
  return user;
}

export function restoreSession(): AuthUser | null {
  const role = window.localStorage.getItem(STORAGE_KEY);
  return role === "DRILLING_ENGINEER" || role === "SYSTEM_ADMIN" ? DEMO_IDENTITIES[role] : null;
}

export function signOut(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
