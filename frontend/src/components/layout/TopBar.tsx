import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, LogOut } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { DEMO_AUTH_LABEL } from "@/auth/authService";
import { homePathFor, roleLabel, ROLES, type Role } from "@/auth/permissions";
import { useHealth } from "@/hooks/useHealth";
import { cn } from "@/lib/utils";
import { StatusDot } from "@/components/nwis/Tags";

function HealthPill() {
  const h = useHealth(30_000);
  const state = h.isLoading ? "unknown" : h.isError ? "crit" : h.data?.data.database === "connected" ? "ok" : "warn";
  const text = h.isLoading ? "Checking API" : h.isError ? "API unreachable" : h.data?.data.database === "connected" ? "API · DB connected" : `DB ${h.data?.data.database}`;
  return (
    <div data-testid="topbar-health" className="flex items-center gap-2 border-l border-line px-3 font-mono text-[10px] uppercase tracking-[0.08em] text-dim" title="GET /health · polled every 30 s">
      <StatusDot state={state} />
      {text}
      {h.data && <span className="text-faint">v{h.data.data.version} · {Math.round(h.data.meta.roundTripMs)} ms</span>}
    </div>
  );
}

function DemoRoleSwitcher() {
  const { user, loginAs } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  if (!user) return null;
  const pick = (r: Role) => {
    setOpen(false);
    if (r === user.role) return;
    loginAs(r);
    navigate(homePathFor(r));
  };
  return (
    <div className="relative border-l border-line">
      <button type="button" data-testid="demo-role-switcher" onClick={() => setOpen(!open)} className="flex h-11 items-center gap-2 border-x border-dashed border-warn/30 bg-warn-deep/30 px-3 font-mono text-[10px] uppercase tracking-[0.08em] text-warn">
        <span className="text-warn/70">Dev mode · role</span>
        {roleLabel(user.role)}
        <ChevronDown className="size-3" />
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-50 w-[260px] border border-line bg-panel">
          <div className="border-b border-dashed border-warn/30 px-3 py-2 font-mono text-[9px] uppercase tracking-[0.12em] text-warn">{DEMO_AUTH_LABEL} · not production security</div>
          {ROLES.map((r) => (
            <button key={r} type="button" data-testid={`demo-role-option-${r}`} onClick={() => pick(r)} className={cn("block w-full px-3 py-2 text-left text-[12px] hover:bg-panel2", r === user.role ? "text-signal" : "text-ink")}>
              {roleLabel(r)}
              <span className="block font-mono text-[9px] text-faint">{r}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function TopBar({ scope, scopeTone }: { scope: string; scopeTone: "signal" | "warn" }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  return (
    <header data-testid="top-bar" className="flex h-11 shrink-0 items-stretch border-b border-line bg-bg">
      <div className="flex items-center gap-3 px-4">
        <span className="font-wide text-[15px] font-bold tracking-[0.12em] text-ink">NWIS</span>
        <span className="hidden font-mono text-[9px] uppercase tracking-[0.14em] text-faint xl:inline">eRTMAC · Nearby Wells Intelligence System</span>
      </div>
      <div className="flex items-center border-l border-line px-3">
        <span data-testid="topbar-role" className={cn("font-mono text-[10px] font-semibold uppercase tracking-[0.14em]", scopeTone === "signal" ? "text-signal" : "text-warn")}>{user.role.replace("_", " ")}</span>
      </div>
      <div className="hidden items-center border-l border-line px-3 font-mono text-[10px] uppercase tracking-[0.1em] text-faint lg:flex" data-testid="topbar-scope">{scope}</div>
      <div className="ml-auto flex items-stretch">
        <HealthPill />
        <DemoRoleSwitcher />
        <div className="flex items-center gap-2.5 border-l border-line px-3">
          <span className="flex size-6 items-center justify-center bg-raised font-mono text-[10px] text-ink">{user.initials}</span>
          <div className="hidden leading-tight md:block">
            <div className="text-[12px]" data-testid="topbar-user-name">{user.name}</div>
            <div className="font-mono text-[9px] text-faint">{user.employeeId}</div>
          </div>
          <button type="button" data-testid="logout-btn" title="Sign out" onClick={() => { logout(); navigate("/login"); }} className="ml-1 flex size-7 items-center justify-center border border-line text-dim transition-colors hover:border-crit/50 hover:text-crit">
            <LogOut className="size-3.5" />
          </button>
        </div>
      </div>
    </header>
  );
}
