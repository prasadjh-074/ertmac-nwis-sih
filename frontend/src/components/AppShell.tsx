import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Activity, Bell, ChevronDown, Database, FileSearch, Gauge, LayoutDashboard, LogOut, Map, Menu, Network, ShieldCheck, SlidersHorizontal, UserRound, Users, Waves, X } from "@/lib/lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./StatusBadge";
import { DEMO_AUTH_LABEL } from "@/auth/authService";
import { roleLabel, roleShortLabel, type Role } from "@/auth/permissions";
import { useAuth } from "@/auth/AuthContext";
import { useState } from "react";

interface NavItem { label: string; path: string; icon: typeof LayoutDashboard; testId: string }

const engineerNav: NavItem[] = [
  { label: "Overview", path: "/engineer", icon: LayoutDashboard, testId: "nav-engineer-overview" },
  { label: "Well intelligence", path: "/engineer/wells", icon: Map, testId: "nav-engineer-wells" },
  { label: "Risk & alerts", path: "/engineer/risk", icon: ShieldCheck, testId: "nav-engineer-risk" },
  { label: "Drilling events", path: "/engineer/events", icon: Waves, testId: "nav-engineer-events" },
  { label: "Documents", path: "/engineer/documents", icon: FileSearch, testId: "nav-engineer-documents" },
];

const adminNav: NavItem[] = [
  { label: "System overview", path: "/admin", icon: LayoutDashboard, testId: "nav-admin-overview" },
  { label: "Users & roles", path: "/admin/users", icon: Users, testId: "nav-admin-users" },
  { label: "Access policies", path: "/admin/policies", icon: SlidersHorizontal, testId: "nav-admin-policies" },
  { label: "Ingestion pipeline", path: "/admin/ingestion", icon: Network, testId: "nav-admin-ingestion" },
  { label: "Database health", path: "/admin/database", icon: Database, testId: "nav-admin-database" },
  { label: "Audit logs", path: "/admin/audit", icon: Activity, testId: "nav-admin-audit" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, switchRole, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  if (!user) return null;
  const isEngineer = user.role === "DRILLING_ENGINEER";
  const navItems = isEngineer ? engineerNav : adminNav;

  const changeRole = (role: Role) => {
    switchRole(role);
    navigate(role === "DRILLING_ENGINEER" ? "/engineer" : "/admin");
    setMobileNavOpen(false);
  };

  const signOut = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-svh bg-slate-100 text-slate-900" data-testid="app-shell">
      <header className="sticky top-0 z-30 flex h-[68px] items-center justify-between border-b border-slate-700 bg-[#0f172a] px-4 text-white shadow-lg lg:px-6" data-testid="app-header">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="text-slate-300 hover:bg-white/10 hover:text-white lg:hidden" onClick={() => setMobileNavOpen((open) => !open)} aria-label="Toggle navigation" data-testid="mobile-navigation-toggle">{mobileNavOpen ? <X size={20} /> : <Menu size={20} />}</Button>
          <Link to={isEngineer ? "/engineer" : "/admin"} className="flex items-center gap-3" data-testid="brand-link">
            <div className="flex size-9 items-center justify-center border border-blue-300/30 bg-blue-500/15 text-blue-200"><Gauge size={19} /></div>
            <div className="hidden sm:block"><p className="text-sm font-bold tracking-[0.16em]">eRTMAC-NWIS</p><p className="text-[10px] text-slate-400">Nearby Wells Intelligence System</p></div>
          </Link>
        </div>
        <div className="hidden min-w-0 flex-1 justify-center px-8 lg:flex"><div className="flex w-full max-w-xl items-center gap-3 border border-slate-700 bg-slate-800/70 px-3 py-2 text-xs text-slate-400" data-testid="global-search-placeholder"><Waves size={15} className="text-blue-300" /><span className="truncate">{isEngineer ? "Ask about wells, formations, risks, or documents" : "System administration workspace"}</span><span className="ml-auto border border-slate-600 px-1.5 py-0.5 font-mono text-[9px] text-slate-500">{isEngineer ? "⌘ K" : "SECURE"}</span></div></div>
        <div className="flex items-center gap-2 sm:gap-4">
          <StatusBadge tone="green" className="hidden border-emerald-400/20 bg-emerald-400/10 text-emerald-300 sm:inline-flex"><span className="size-1.5 rounded-full bg-emerald-400" /> Demo environment</StatusBadge>
          <button className="relative p-2 text-slate-300 transition-colors duration-150 hover:text-white" aria-label="Notifications" data-testid="notifications-button"><Bell size={18} /><span className="absolute right-1 top-1 size-1.5 rounded-full bg-amber-400" /></button>
          <div className="group relative">
            <button className="flex items-center gap-2 border-l border-slate-700 pl-3 text-left" data-testid="user-menu-button"><span className="flex size-8 items-center justify-center rounded-full bg-blue-500/25 text-xs font-bold text-blue-100">{user.initials}</span><span className="hidden md:block"><span className="block text-xs font-semibold text-white">{user.name}</span><span className="block text-[10px] text-slate-400">{roleShortLabel(user.role)}</span></span><ChevronDown size={14} className="text-slate-500" /></button>
            <div className="invisible absolute right-0 top-12 w-64 translate-y-1 border border-slate-200 bg-white p-2 text-slate-800 opacity-0 shadow-xl transition-all duration-150 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100 group-hover:visible group-hover:translate-y-0 group-hover:opacity-100" data-testid="role-switcher-menu">
              <p className="px-3 pb-2 pt-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">{DEMO_AUTH_LABEL}</p>
              <button className={`flex w-full items-center justify-between px-3 py-2 text-left text-xs transition-colors duration-150 hover:bg-slate-50 ${user.role === "DRILLING_ENGINEER" ? "bg-blue-50 text-blue-700" : "text-slate-600"}`} onClick={() => changeRole("DRILLING_ENGINEER")} data-testid="role-switch-engineer-button">{roleLabel("DRILLING_ENGINEER")}{user.role === "DRILLING_ENGINEER" ? "✓" : ""}</button>
              <button className={`flex w-full items-center justify-between px-3 py-2 text-left text-xs transition-colors duration-150 hover:bg-slate-50 ${user.role === "SYSTEM_ADMIN" ? "bg-blue-50 text-blue-700" : "text-slate-600"}`} onClick={() => changeRole("SYSTEM_ADMIN")} data-testid="role-switch-admin-button">{roleLabel("SYSTEM_ADMIN")}{user.role === "SYSTEM_ADMIN" ? "✓" : ""}</button>
              <div className="my-2 border-t border-slate-100" />
              <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-semibold text-red-600 transition-colors duration-150 hover:bg-red-50" onClick={signOut} data-testid="sign-out-button"><LogOut size={14} /> Sign out</button>
            </div>
          </div>
        </div>
      </header>
      <div className="flex">
        <aside className={`fixed inset-y-[68px] left-0 z-20 w-64 border-r border-slate-700 bg-[#1e293b] px-3 py-5 transition-transform duration-200 lg:sticky lg:top-[68px] lg:block lg:h-[calc(100vh-68px)] lg:translate-x-0 ${mobileNavOpen ? "translate-x-0" : "-translate-x-full"}`} data-testid="sidebar-navigation">
          <div className="mb-5 px-3"><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">{isEngineer ? "Operational workspace" : "Administration"}</p><p className="mt-1 text-xs text-slate-400">{isEngineer ? "Evidence-first investigation" : "Platform controls only"}</p></div>
          <nav className="space-y-1" aria-label="Primary navigation">
            {navItems.map(({ label, path, icon: Icon, testId }) => {
              const active = location.pathname === path || (path !== (isEngineer ? "/engineer" : "/admin") && location.pathname.startsWith(path));
              return <Link key={path} to={path} onClick={() => setMobileNavOpen(false)} className={`group flex items-center gap-3 border-l-2 px-3 py-2.5 text-sm transition-colors duration-150 ${active ? "border-blue-400 bg-blue-500/15 font-semibold text-white" : "border-transparent text-slate-400 hover:bg-white/5 hover:text-slate-100"}`} data-testid={testId}><Icon size={17} className={active ? "text-blue-300" : "text-slate-500 group-hover:text-slate-300"} /><span>{label}</span>{active && <span className="ml-auto size-1.5 rounded-full bg-blue-300" />}</Link>;
            })}
          </nav>
          <div className="absolute bottom-5 left-3 right-3 border-t border-slate-700 pt-4"><div className="flex items-start gap-2 px-3 text-[10px] leading-relaxed text-slate-500"><UserRound size={14} className="mt-0.5 shrink-0 text-slate-600" /><span><strong className="font-semibold text-slate-400">{roleLabel(user.role)}</strong><br />Frontend role controls are UX only. Backend authorization remains the security boundary.</span></div></div>
        </aside>
        <main className="min-w-0 flex-1" data-testid="main-content">{children}</main>
      </div>
    </div>
  );
}