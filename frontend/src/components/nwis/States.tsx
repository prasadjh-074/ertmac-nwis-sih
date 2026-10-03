import type { ReactNode } from "react";
import { AlertTriangle, CircleSlash, Lock, ServerCrash, TimerOff } from "lucide-react";
import { ApiError } from "@/api/client";
import { cn } from "@/lib/utils";

export function SkeletonLines({ rows = 3, label, className }: { rows?: number; label?: string; className?: string }) {
  return (
    <div className={cn("space-y-2 p-3", className)} data-testid="skeleton">
      {label && <div className="label mb-2">{label}</div>}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-3" style={{ width: `${92 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}

export function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function EmptyState({ title, hint, icon, testid }: { title: string; hint?: ReactNode; icon?: ReactNode; testid?: string }) {
  return (
    <div data-testid={testid ?? "empty-state"} className="flex h-full min-h-[96px] flex-col items-start justify-center gap-1 px-4 py-5">
      <div className="flex items-center gap-2 text-dim">
        {icon ?? <CircleSlash className="size-3.5" strokeWidth={1.5} />}
        <span className="font-mono text-[11px] uppercase tracking-[0.1em]">{title}</span>
      </div>
      {hint && <p className="max-w-md text-[12px] leading-relaxed text-faint">{hint}</p>}
    </div>
  );
}

function describe(error: unknown): { icon: ReactNode; headline: string; body: string; requestId: string | null } {
  if (error instanceof ApiError) {
    if (error.type === "timeout" || error.status === 504)
      return {
        icon: <TimerOff className="size-4" strokeWidth={1.5} />,
        headline: "Backend timeout",
        body: "The API did not respond in time. A hosted backend on a free tier can take ~30 s to wake up. Retry shortly.",
        requestId: error.requestId,
      };
    if (error.status === 401 || error.status === 403)
      return { icon: <Lock className="size-4" strokeWidth={1.5} />, headline: "Outside authorization scope", body: "This resource is outside your authorization scope.", requestId: error.requestId };
    if (error.status === 404) return { icon: <CircleSlash className="size-4" strokeWidth={1.5} />, headline: "Not found", body: error.message, requestId: error.requestId };
    if (error.status === 0 || error.status >= 500)
      return { icon: <ServerCrash className="size-4" strokeWidth={1.5} />, headline: "Service unavailable", body: error.message, requestId: error.requestId };
    return { icon: <AlertTriangle className="size-4" strokeWidth={1.5} />, headline: `Request failed · ${error.status}`, body: error.message, requestId: error.requestId };
  }
  return { icon: <AlertTriangle className="size-4" strokeWidth={1.5} />, headline: "Unexpected error", body: error instanceof Error ? error.message : String(error), requestId: null };
}

export function ErrorState({ error, context, onRetry, testid }: { error: unknown; context?: string; onRetry?: () => void; testid?: string }) {
  const d = describe(error);
  return (
    <div data-testid={testid ?? "error-state"} className="m-3 border border-crit/30 bg-crit-deep/40 px-3 py-2.5">
      <div className="flex items-center gap-2 text-crit">
        {d.icon}
        <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.1em]">{d.headline}</span>
      </div>
      {context && <p className="mt-1.5 text-[12px] text-ink">{context}</p>}
      <p className="mt-1 text-[12px] leading-relaxed text-dim">{d.body}</p>
      <div className="mt-2 flex items-center gap-3">
        {d.requestId && <span className="font-mono text-[10px] text-faint" data-testid="error-request-id">REQUEST ID {d.requestId}</span>}
        {onRetry && (
          <button type="button" onClick={onRetry} data-testid="error-retry-btn" className="ml-auto font-mono text-[10px] uppercase tracking-[0.1em] text-signal hover:underline">
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

export function RestrictedNotice({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex items-start gap-3 border border-line bg-panel2 px-4 py-3">
      <Lock className="mt-0.5 size-4 text-faint" strokeWidth={1.5} />
      <div>
        <div className="font-mono text-[11px] uppercase tracking-[0.1em] text-dim">{title}</div>
        <p className="mt-1 text-[12px] text-faint">{body}</p>
      </div>
    </div>
  );
}
