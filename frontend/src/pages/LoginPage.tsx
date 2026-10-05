import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, HardHat, ServerCog } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { DEMO_AUTH_LABEL } from "@/auth/authService";
import { homePathFor, type Role } from "@/auth/permissions";
import { useHealth } from "@/hooks/useHealth";
import { StatusDot } from "@/components/nwis/Tags";

const CAPABILITIES = [
  ["01", "Offset wells", "Haversine radius search and log-embedding similarity"],
  ["02", "Drilling history", "Events extracted from SODIR narratives, with source snippet"],
  ["03", "Risk evidence", "Rule-based scores with methodology and limitations"],
  ["04", "Investigation", "Natural-language questions answered from evidence, not generated"],
];

function SystemLine() {
  const h = useHealth(false);
  const state = h.isLoading ? "unknown" : h.isError ? "crit" : "ok";
  return (
    <div data-testid="login-system-status" className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
      <StatusDot state={state} />
      {h.isLoading ? "Contacting API… a sleeping backend can take ~30 s" : h.isError ? "API unreachable" : `API v${h.data?.data.version} · database ${h.data?.data.database}`}
    </div>
  );
}

function RoleButton({ role, icon: Icon, title, desc, onPick }: { role: Role; icon: typeof HardHat; title: string; desc: string; onPick: (r: Role) => void }) {
  return (
    <button type="button" data-testid={`demo-login-${role}`} onClick={() => onPick(role)} className="group flex w-full items-center gap-3 border border-line bg-panel2 px-3 py-3 text-left transition-colors hover:border-signal/60">
      <Icon className="size-5 text-faint transition-colors group-hover:text-signal" strokeWidth={1.5} />
      <div className="flex-1">
        <div className="text-[13px] font-medium">{title}</div>
        <div className="font-mono text-[10px] text-faint">{role} · {desc}</div>
      </div>
      <ArrowRight className="size-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-signal" />
    </button>
  );
}

export default function LoginPage() {
  const { user, loginAs } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [notice, setNotice] = useState(false);
  if (user) return <Navigate to={homePathFor(user.role)} replace />;

  const from = (location.state as { from?: string } | null)?.from;
  const pick = (r: Role) => {
    loginAs(r);
    navigate(from && from.startsWith(homePathFor(r)) ? from : homePathFor(r), { replace: true });
  };

  return (
    <div data-testid="login-page" className="grid min-h-full grid-cols-1 bg-bg lg:grid-cols-[minmax(0,1.35fr)_minmax(420px,1fr)]">
      <section className="gridlines relative hidden flex-col justify-between border-r border-line p-12 lg:flex">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-faint">SIH 2026 · PS 26121 · Oil India Limited</div>
        <div className="rise">
          <div className="font-mono text-[11px] uppercase tracking-[0.24em] text-signal">Drilling intelligence platform</div>
          <h1 className="font-wide mt-3 text-[112px] font-extrabold leading-[0.85] tracking-[-0.01em] text-ink">NWIS</h1>
          <p className="font-semicond mt-4 text-[22px] font-light text-dim">Nearby Wells Intelligence System</p>
          <div className="mt-12 grid max-w-2xl grid-cols-2 gap-px border border-line bg-line">
            {CAPABILITIES.map(([n, t, d]) => (
              <div key={n} className="bg-bg/95 p-4">
                <div className="font-mono text-[10px] text-signal">{n}</div>
                <div className="mt-1 text-[13px] font-medium">{t}</div>
                <div className="mt-0.5 text-[12px] leading-relaxed text-faint">{d}</div>
              </div>
            ))}
          </div>
        </div>
        <SystemLine />
      </section>

      <section className="flex items-center justify-center p-8">
        <div className="w-full max-w-[380px]">
          <div className="lg:hidden">
            <h1 className="font-wide text-[48px] font-extrabold leading-none">NWIS</h1>
            <p className="mt-1 text-dim">Nearby Wells Intelligence System</p>
          </div>
          <div className="label mt-8 lg:mt-0">Secure organizational access</div>
          <form className="mt-4 space-y-3" onSubmit={(e) => { e.preventDefault(); setNotice(true); }}>
            <label className="block">
              <span className="label">Employee ID / Username</span>
              <input data-testid="login-username-input" autoComplete="username" placeholder="engineer@oilindia" className="mt-1 h-9 w-full border border-line bg-panel2 px-3 font-mono text-[13px] outline-none placeholder:text-faint focus:border-signal/60" />
            </label>
            <label className="block">
              <span className="label">Password</span>
              <input data-testid="login-password-input" type="password" autoComplete="current-password" placeholder="••••••••••" className="mt-1 h-9 w-full border border-line bg-panel2 px-3 font-mono text-[13px] outline-none placeholder:text-faint focus:border-signal/60" />
            </label>
            <button type="submit" data-testid="login-submit-btn" className="h-9 w-full bg-signal font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#061014] transition-colors hover:bg-[#5ad6e5]">Sign in</button>
            {notice && (
              <p data-testid="login-sso-notice" className="border border-warn/40 bg-warn-deep/50 px-3 py-2 text-[12px] text-warn">
                Credential sign-in requires organizational SSO, which is not connected yet. Use demo access below.
              </p>
            )}
          </form>

          <div className="mt-8 border border-dashed border-warn/40 p-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-warn">{DEMO_AUTH_LABEL}</span>
              <span className="font-mono text-[9px] text-faint">not production security</span>
            </div>
            <div className="mt-3 space-y-1.5">
              <RoleButton role="DRILLING_ENGINEER" icon={HardHat} title="Drilling Engineer" desc="operational workspace" onPick={pick} />
              <RoleButton role="SYSTEM_ADMIN" icon={ServerCog} title="System Administrator" desc="platform administration" onPick={pick} />
            </div>
          </div>
          <div className="mt-6 lg:hidden"><SystemLine /></div>
        </div>
      </section>
    </div>
  );
}
