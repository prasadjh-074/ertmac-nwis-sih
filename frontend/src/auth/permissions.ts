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

const permissionsByRole: Record<Role, readonly Permission[]> = {
  DRILLING_ENGINEER: [
    "VIEW_WELLS",
    "VIEW_NEARBY_WELLS",
    "VIEW_SIMILAR_WELLS",
    "VIEW_EVENTS",
    "VIEW_RISK",
    "VIEW_ALERTS",
    "VIEW_DOCUMENTS",
    "USE_AI_QUERY",
    "VIEW_PROVENANCE",
  ],
  SYSTEM_ADMIN: [
    "MANAGE_USERS",
    "MANAGE_ROLES",
    "VIEW_AUDIT_LOGS",
    "VIEW_SYSTEM_HEALTH",
    "VIEW_DATABASE_HEALTH",
    "VIEW_INGESTION",
  ],
};

export function hasPermission(role: Role, permission: Permission): boolean {
  return permissionsByRole[role].includes(permission);
}

export function roleLabel(role: Role): string {
  return role === "DRILLING_ENGINEER" ? "Drilling Engineer" : "System Administrator";
}

export function roleShortLabel(role: Role): string {
  return role === "DRILLING_ENGINEER" ? "ENGINEER" : "ADMIN";
}