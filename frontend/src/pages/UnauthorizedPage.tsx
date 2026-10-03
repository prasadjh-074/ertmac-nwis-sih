import { Link } from "react-router-dom";
import { Lock } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { homePathFor, roleLabel } from "@/auth/permissions";

export default function UnauthorizedPage() {
  const { user } = useAuth();
  return (
    <div data-testid="unauthorized-page" className="flex h-full min-h-[60vh] items-center justify-center bg-bg p-8">
      <div className="w-full max-w-lg border border-line bg-panel">
        <div className="hatch h-2 border-b border-line" />
        <div className="p-6">
          <div className="flex items-center gap-2 text-warn"><Lock className="size-4" /><span className="font-mono text-[11px] uppercase tracking-[0.16em]">Access restricted</span></div>
          <h1 className="mt-3 font-semicond text-[22px] font-semibold">This resource is outside your authorization scope.</h1>
          <p className="mt-2 text-[13px] text-dim">
            {user ? `Your role (${roleLabel(user.role)}) does not include the permission this area requires.` : "Sign in to continue."} The attempt has been recorded in the local session log.
          </p>
          <Link to={user ? homePathFor(user.role) : "/login"} data-testid="unauthorized-home-link" className="mt-5 inline-flex h-8 items-center border border-line px-3 font-mono text-[11px] uppercase tracking-[0.1em] text-ink transition-colors hover:border-signal/60 hover:text-signal">
            Return to your workspace
          </Link>
        </div>
      </div>
    </div>
  );
}
