import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import { Activity, Database, FileClock, KeyRound, LayoutGrid, ShieldCheck, Users, Workflow } from "lucide-react";
import { RequirePermission } from "@/auth/RoleGuard";
import { TopBar } from "@/components/layout/TopBar";
import { SideNav, type NavItem } from "@/components/layout/SideNav";
import UnauthorizedPage from "./UnauthorizedPage";
import { AdminTelemetryProvider } from "@/features/administration/AdminTelemetry";
import { AdminOverview } from "@/features/administration/AdminOverview";
import { AccessPolicies, UsersRoles } from "@/features/administration/UsersPolicies";
import { AuditLogs, DatabaseHealth, IngestionPipeline, SecurityPosture, SystemHealth } from "@/features/administration/AdminPages";

const NAV: NavItem[] = [
  { to: "/admin", label: "Overview", icon: LayoutGrid, permission: "VIEW_SYSTEM_HEALTH", code: "00" },
  { to: "/admin/users", label: "Users & Roles", icon: Users, permission: "MANAGE_USERS", code: "01" },
  { to: "/admin/policies", label: "Access Policies", icon: KeyRound, permission: "MANAGE_ROLES", code: "02" },
  { to: "/admin/ingestion", label: "Ingestion Pipeline", icon: Workflow, permission: "VIEW_INGESTION", code: "03" },
  { to: "/admin/health", label: "System Health", icon: Activity, permission: "VIEW_SYSTEM_HEALTH", code: "04" },
  { to: "/admin/database", label: "Database Health", icon: Database, permission: "VIEW_DATABASE_HEALTH", code: "05" },
  { to: "/admin/audit", label: "Audit Logs", icon: FileClock, permission: "VIEW_AUDIT_LOGS", code: "06" },
  { to: "/admin/security", label: "Security", icon: ShieldCheck, permission: "MANAGE_ROLES", code: "07" },
];

export default function AdminDashboard() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <AdminTelemetryProvider>
      <div className="flex h-full min-h-0 flex-col" data-testid="admin-app">
        <TopBar scope="System administration · operational drilling intelligence restricted" scopeTone="warn" />
        <div className="flex min-h-0 flex-1">
          <SideNav title="Administration" items={NAV} collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}
            footer={<p className="font-mono text-[9px] leading-relaxed text-faint">Platform permissions only. Well data, risk and engineering reports are outside this role's scope.</p>} />
          <main className="min-w-0 flex-1 overflow-auto bg-bg">
            <Routes>
              <Route index element={<RequirePermission permission="VIEW_SYSTEM_HEALTH"><AdminOverview /></RequirePermission>} />
              <Route path="users" element={<RequirePermission permission="MANAGE_USERS"><UsersRoles /></RequirePermission>} />
              <Route path="policies" element={<RequirePermission permission="MANAGE_ROLES"><AccessPolicies /></RequirePermission>} />
              <Route path="ingestion" element={<RequirePermission permission="VIEW_INGESTION"><IngestionPipeline /></RequirePermission>} />
              <Route path="health" element={<RequirePermission permission="VIEW_SYSTEM_HEALTH"><SystemHealth /></RequirePermission>} />
              <Route path="database" element={<RequirePermission permission="VIEW_DATABASE_HEALTH"><DatabaseHealth /></RequirePermission>} />
              <Route path="audit" element={<RequirePermission permission="VIEW_AUDIT_LOGS"><AuditLogs /></RequirePermission>} />
              <Route path="security" element={<RequirePermission permission="MANAGE_ROLES"><SecurityPosture /></RequirePermission>} />
              <Route path="*" element={<UnauthorizedPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </AdminTelemetryProvider>
  );
}
