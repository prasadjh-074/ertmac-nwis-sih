import { Check, Minus } from "lucide-react";
import { demoIdentities } from "@/auth/authService";
import { OPERATIONAL_PERMISSIONS, PERMISSIONS_BY_ROLE, PLATFORM_PERMISSIONS, ROLES, roleLabel } from "@/auth/permissions";
import { readSessionLog } from "@/lib/sessionLog";
import { shortTime } from "@/lib/format";
import { Panel, ToolButton } from "@/components/nwis/Panel";
import { DataTag, Tag } from "@/components/nwis/Tags";

const ACTIONS = ["View", "Edit role", "Suspend", "Manage access"];

export function UsersRoles() {
  const log = readSessionLog();
  const lastLogin = (id: string) => log.find((e) => e.actor === id && e.action.startsWith("Signed in"))?.ts;
  return (
    <div data-testid="admin-users" className="flex min-h-full flex-col gap-1.5 p-1.5">
      <Panel code="U-01" title="Users" meta="no user-directory API" testid="users-panel" actions={<DataTag kind="demo" />}>
        <table className="w-full text-left text-[12px]" data-testid="users-table">
          <thead className="bg-panel font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
            <tr className="border-b border-line"><th className="px-3 py-1.5">Name</th><th>Employee ID</th><th>Department</th><th>Role</th><th>Status</th><th>Last login</th><th>Access scope</th><th>Actions</th></tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {demoIdentities().map((u) => (
              <tr key={u.id} data-testid={`user-row-${u.employeeId}`}>
                <td className="px-3 py-2">{u.name}</td>
                <td className="font-mono">{u.employeeId}</td>
                <td className="text-dim">{u.department}</td>
                <td><Tag tone={u.role === "SYSTEM_ADMIN" ? "warn" : "info"}>{u.role}</Tag></td>
                <td><Tag className="border-dashed">Demo identity</Tag></td>
                <td className="font-mono text-[10px] text-dim">{lastLogin(u.employeeId) ? shortTime(lastLogin(u.employeeId)!) : "—"}</td>
                <td className="text-dim">{u.role === "DRILLING_ENGINEER" ? "Operational" : "Platform"}</td>
                <td className="pr-3"><div className="flex gap-1">{ACTIONS.map((a) => <ToolButton key={a} disabled title="Backend endpoint pending" testid={`user-action-${a.toLowerCase().replace(/ /g, "-")}-${u.employeeId}`}>{a}</ToolButton>)}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="px-3 py-2 font-mono text-[10px] text-faint">These are the two built-in demo identities used by demo authentication. User management actions are disabled · backend endpoint pending.</p>
      </Panel>
      <Panel code="U-02" title="Roles" testid="roles-panel">
        <div className="grid grid-cols-1 gap-px bg-line md:grid-cols-2">
          {ROLES.map((r) => (
            <div key={r} className="bg-panel p-3" data-testid={`role-card-${r}`}>
              <div className="flex items-center gap-2"><span className="font-mono text-[12px]">{r}</span><span className="text-[12px] text-dim">· {roleLabel(r)}</span></div>
              <div className="mt-2 flex flex-wrap gap-1">{PERMISSIONS_BY_ROLE[r].map((p) => <Tag key={p}>{p}</Tag>)}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Cell({ on }: { on: boolean }) {
  return on ? <Check className="mx-auto size-3.5 text-ok" /> : <Minus className="mx-auto size-3.5 text-faint" />;
}

export function AccessPolicies() {
  return (
    <div data-testid="admin-policies" className="flex min-h-full flex-col gap-1.5 p-1.5">
      <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel code="P-01" title="Data domain separation" testid="policy-domain-panel" meta="source · src/auth/permissions.ts">
          <table className="w-full text-left text-[12px]">
            <thead className="font-mono text-[9px] uppercase tracking-[0.08em] text-faint"><tr className="border-b border-line"><th className="px-3 py-1.5">Role</th><th>Operational data</th><th>System data</th></tr></thead>
            <tbody className="divide-y divide-line-soft">
              <tr><td className="px-3 py-2 font-mono">DRILLING_ENGINEER</td><td><Tag tone="ok">Granted</Tag></td><td><Tag>Health indicator only</Tag></td></tr>
              <tr><td className="px-3 py-2 font-mono">SYSTEM_ADMIN</td><td><Tag tone="crit">Restricted</Tag></td><td><Tag tone="ok">Granted</Tag></td></tr>
            </tbody>
          </table>
          <p className="px-3 py-2 text-[12px] text-dim">Administrators do not inherit operational permissions. Separation of duties is a product rule, not a convenience default.</p>
        </Panel>
        <Panel code="P-02" title="Well & document scopes" testid="policy-scope-panel" actions={<DataTag kind="pending" />}>
          <div className="grid grid-cols-2 gap-px bg-line">
            {demoIdentities().map((u) => (
              <div key={u.id} className="space-y-2 bg-panel p-3">
                <div className="font-mono text-[12px]">{u.employeeId}</div>
                <div className="grid grid-cols-2 gap-2 text-[12px]">
                  <span className="label">Role</span><span className="font-mono text-[11px]">{u.role}</span>
                  <span className="label">Authorized wells</span><span className="font-mono text-faint">— pending</span>
                  <span className="label">Authorized docs</span><span className="font-mono text-faint">— pending</span>
                  <span className="label">Access level</span><span>{u.role === "DRILLING_ENGINEER" ? "Operational" : "Platform"}</span>
                </div>
              </div>
            ))}
          </div>
          <p className="px-3 py-2 font-mono text-[10px] text-faint">Per-well and per-document ACLs require a backend authorization service. None is exposed yet.</p>
        </Panel>
      </div>
      <Panel code="P-03" title="Permission matrix" testid="policy-matrix-panel" meta="enforced in the UI · backend enforcement pending">
        <table className="w-full text-center text-[12px]" data-testid="permission-matrix">
          <thead className="font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
            <tr className="border-b border-line"><th className="px-3 py-1.5 text-left">Permission</th><th className="text-left">Domain</th>{ROLES.map((r) => <th key={r}>{r}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {[...OPERATIONAL_PERMISSIONS, ...PLATFORM_PERMISSIONS].map((p) => (
              <tr key={p}>
                <td className="px-3 py-1.5 text-left font-mono text-[11px]">{p}</td>
                <td className="text-left text-dim">{OPERATIONAL_PERMISSIONS.includes(p) ? "Operational" : "Platform"}</td>
                {ROLES.map((r) => <td key={r}><Cell on={PERMISSIONS_BY_ROLE[r].includes(p)} /></td>)}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="px-3 py-2 font-mono text-[10px] text-faint">Frontend authorization is UX only — the backend currently performs no identity checks.</p>
      </Panel>
    </div>
  );
}
