import type { Role } from "./permissions";

const DEMO_ROLE_KEY = "nwis-demo-role";

export const DEMO_AUTH_LABEL = "DEMO AUTHENTICATION · LOCAL ONLY";

export function readDemoRole(): Role | null {
  const storedRole = window.localStorage.getItem(DEMO_ROLE_KEY);
  return storedRole === "DRILLING_ENGINEER" || storedRole === "SYSTEM_ADMIN" ? storedRole : null;
}

export function persistDemoRole(role: Role): void {
  window.localStorage.setItem(DEMO_ROLE_KEY, role);
}

export function clearDemoRole(): void {
  window.localStorage.removeItem(DEMO_ROLE_KEY);
}

// TODO(auth): Replace demo authentication with organizational SSO/JWT.