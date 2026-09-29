import { Link } from "react-router-dom";
import { ArrowLeft, ShieldX } from "@/lib/lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { useAuth } from "@/auth/AuthContext";

export default function UnauthorizedPage() {
  const { user } = useAuth();
  const target = user?.role === "SYSTEM_ADMIN" ? "/admin" : "/engineer";
  return <div className="flex min-h-svh items-center justify-center bg-slate-100 p-6" data-testid="unauthorized-page"><div className="max-w-md border border-slate-200 bg-white p-8 text-center shadow-sm"><div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-red-50 text-red-600"><ShieldX size={22} /></div><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-red-600">Access boundary</p><h1 className="mt-3 text-2xl font-bold text-slate-900">This resource is outside your authorization scope.</h1><p className="mt-3 text-sm leading-relaxed text-slate-500">Your current demo role does not include this workspace. Frontend authorization is a UX boundary; backend authorization remains the security boundary.</p><Link to={target} className={buttonVariants({ variant: "outline", className: "mt-6" })} data-testid="unauthorized-return-button"><ArrowLeft size={15} /> Return to workspace</Link></div></div>;
}