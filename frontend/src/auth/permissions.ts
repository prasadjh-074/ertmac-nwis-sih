export type Role = "DRILLING_ENGINEER" | "SYSTEM_ADMIN";

export type Permission =
  | "VIEW_WELLS"
  | "VIEW_NEARBY_WELLS"
  | "VIEW_SIMILAR_WELLS"
  | "VIEW_EVENTS"
  | "VIEW_RISK"
  | "VIEW_ALERTS"
  | "VIEW_DOCUMENTS"
  | "USE_AI_QUERY"
  | "VIEW_PROVENANCE"
  | "MANAGE_USERS"
  | "MANAGE_ROLES"
  | "VIEW_AUDIT_LOGS"
  | "VIEW_SYSTEM_HEALTH"
  | "VIEW_DATABASE_HEALTH"
  | "VIEW_INGESTION";

export const OPERATIONAL_PERMISSIONS: readonly Permission[] = [
  "VIEW_WELLS",
  "VIEW_NEARBY_WELLS",
  "VIEW_SIMILAR_WELLS",
  "VIEW_EVENTS",
  "VIEW_RISK",
  "VIEW_ALERTS",
  "VIEW_DOCUMENTS",
  "USE_AI_QUERY",
  "VIEW_PROVENANCE",
];

export const PLATFORM_PERMISSIONS: readonly Permission[] = [
  "MANAGE_USERS",
  "MANAGE_ROLES",
  "VIEW_AUDIT_LOGS",
  "VIEW_SYSTEM_HEALTH",
  "VIEW_DATABASE_HEALTH",
  "VIEW_INGESTION",
];

// Separation of duties: admins never inherit operational data permissions.
export const PERMISSIONS_BY_ROLE: Record<Role, readonly Permission[]> = {
  DRILLING_ENGINEER: [...OPERATIONAL_PERMISSIONS],
  SYSTEM_ADMIN: [...PLATFORM_PERMISSIONS],
};

export const ROLES: readonly Role[] = ["DRILLING_ENGINEER", "SYSTEM_ADMIN"];

export function hasPermission(role: Role | null | undefined, permission: Permission): boolean {
  return !!role && PERMISSIONS_BY_ROLE[role].includes(permission);
}

export function roleLabel(role: Role): string {
  return role === "DRILLING_ENGINEER" ? "Drilling Engineer" : "System Administrator";
}

export function homePathFor(role: Role): string {
  return role === "DRILLING_ENGINEER" ? "/engineer" : "/admin";
}
