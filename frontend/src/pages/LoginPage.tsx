import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, CheckCircle2, Database, Gauge, LockKeyhole, ShieldCheck, Waves } from "@/lib/lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { DEMO_AUTH_LABEL } from "@/auth/authService";
import { useAuth } from "@/auth/AuthContext";
import type { Role } from "@/auth/permissions";

export default function LoginPage() {
  const { loginAs } = useAuth();
  const navigate = useNavigate();
  const [role, setRole] = useState<Role>("DRILLING_ENGINEER");
  const [employeeId, setEmployeeId] = useState("");

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loginAs(role);
    navigate(role === "DRILLING_ENGINEER" ? "/engineer" : "/admin");
  };

  return (
    <div className="grid min-h-svh bg-slate-100 lg:grid-cols-[minmax(360px,0.82fr)_1.18fr]" data-testid="login-page">
      <section className="relative hidden overflow-hidden bg-[#0f172a] p-10 text-white lg:flex lg:flex-col lg:justify-between" data-testid="login-brand-panel">
        <div className="absolute -right-24 top-20 size-80 rounded-full border border-blue-400/10" /><div className="absolute -right-12 top-32 size-56 rounded-full border border-blue-400/10" /><div className="absolute bottom-24 left-10 h-px w-[420px] bg-gradient-to-r from-blue-400/40 to-transparent" />
        <div className="relative"><div className="mb-16 flex items-center gap-3"><div className="flex size-11 items-center justify-center border border-blue-300/30 bg-blue-400/10 text-blue-200"><Gauge size={22} /></div><div><p className="text-lg font-bold tracking-[0.18em]">eRTMAC-NWIS</p><p className="text-xs text-slate-400">Nearby Wells Intelligence System</p></div></div><p className="mb-3 text-[11px] font-bold uppercase tracking-[0.26em] text-blue-300">Drilling intelligence platform</p><h1 className="max-w-md text-4xl font-bold leading-tight tracking-tight">Evidence before the next drilling decision.</h1><p className="mt-5 max-w-md text-sm leading-7 text-slate-400">Connect wells, historical events, geological context and explainable risk in one operational workspace.</p></div>
        <div className="relative grid grid-cols-3 gap-3 border-t border-slate-700 pt-5 text-xs"><div><Waves size={16} className="mb-2 text-blue-300" /><p className="font-semibold">Well context</p><p className="mt-1 text-slate-500">Traceable data</p></div><div><ShieldCheck size={16} className="mb-2 text-emerald-300" /><p className="font-semibold">Role aware</p><p className="mt-1 text-slate-500">Scoped access</p></div><div><Database size={16} className="mb-2 text-amber-300" /><p className="font-semibold">Provenance</p><p className="mt-1 text-slate-500">Source first</p></div></div>
      </section>
      <section className="flex items-center justify-center p-5 sm:p-10" data-testid="login-form-panel">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden"><p className="text-lg font-bold tracking-[0.18em] text-[#0f172a]">eRTMAC-NWIS</p><p className="text-xs text-slate-500">Nearby Wells Intelligence System</p></div>
          <div className="mb-8"><StatusBadge tone="amber">{DEMO_AUTH_LABEL}</StatusBadge><h2 className="mt-4 text-3xl font-bold tracking-tight text-slate-900">Secure workspace access</h2><p className="mt-2 text-sm leading-relaxed text-slate-500">Choose a development role to preview the permission-aware workstation. No production credentials are processed here.</p></div>
          <form onSubmit={submit} className="space-y-5" data-testid="login-form">
            <div><label htmlFor="employee-id" className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-600">Employee ID / username</label><Input id="employee-id" value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} placeholder="engineer@organization" className="h-11 border-slate-300 bg-white" data-testid="login-employee-input" /></div>
            <div><label htmlFor="password" className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-600">Password</label><div className="relative"><LockKeyhole size={16} className="absolute left-3 top-3.5 text-slate-400" /><Input id="password" type="password" placeholder="Demo access does not validate credentials" className="h-11 border-slate-300 bg-white pl-9" data-testid="login-password-input" /></div></div>
            <div><p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-600">Preview role</p><div className="grid gap-2 sm:grid-cols-2"><button type="button" onClick={() => setRole("DRILLING_ENGINEER")} className={`border p-3 text-left transition-colors duration-150 ${role === "DRILLING_ENGINEER" ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 bg-white hover:border-blue-300"}`} data-testid="login-engineer-role-button"><span className="flex items-center justify-between text-sm font-semibold text-slate-800">Drilling Engineer {role === "DRILLING_ENGINEER" && <CheckCircle2 size={16} className="text-blue-600" />}</span><span className="mt-1 block text-xs text-slate-500">Operational intelligence</span></button><button type="button" onClick={() => setRole("SYSTEM_ADMIN")} className={`border p-3 text-left transition-colors duration-150 ${role === "SYSTEM_ADMIN" ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 bg-white hover:border-blue-300"}`} data-testid="login-admin-role-button"><span className="flex items-center justify-between text-sm font-semibold text-slate-800">System Administrator {role === "SYSTEM_ADMIN" && <CheckCircle2 size={16} className="text-blue-600" />}</span><span className="mt-1 block text-xs text-slate-500">Platform controls only</span></button></div></div>
            <Button type="submit" className="h-11 w-full bg-blue-600 font-semibold shadow-sm hover:bg-blue-700" data-testid="login-submit-button">Enter {role === "DRILLING_ENGINEER" ? "engineer" : "admin"} workspace <ArrowRight size={16} /></Button>
          </form>
          <div className="mt-8 flex items-center gap-2 border-t border-slate-200 pt-4 text-xs text-slate-500"><LockKeyhole size={14} className="text-emerald-600" /> Replace this demo boundary with organizational SSO/JWT before production use.</div>
        </div>
      </section>
    </div>
  );
}