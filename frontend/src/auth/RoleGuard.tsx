import { useEffect, type ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import UnauthorizedPage from "@/pages/UnauthorizedPage";
import { logSessionEvent } from "@/lib/sessionLog";
import { useAuth } from "./AuthContext";
import type { Permission } from "./permissions";

function Denied({ path }: { path: string }) {
  const { user } = useAuth();
  useEffect(() => {
    if (user) logSessionEvent(user.employeeId, "Route access", path, "Denied");
  }, [user, path]);
  return <UnauthorizedPage />;
}

export function RequirePermission({ permission, children }: { permission: Permission; children?: ReactNode }) {
  const { user, can } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!can(permission)) return <Denied path={location.pathname} />;
  return children ? <>{children}</> : <Outlet />;
}

export function RoleGate({ permission, children, fallback = null }: { permission: Permission; children: ReactNode; fallback?: ReactNode }) {
  const { can } = useAuth();
  return <>{can(permission) ? children : fallback}</>;
}
