import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "blue" | "green" | "amber" | "red" | "slate";

const toneClasses: Record<Tone, string> = {
  blue: "border-blue-200 bg-blue-50 text-blue-700",
  green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-red-200 bg-red-50 text-red-700",
  slate: "border-slate-200 bg-slate-100 text-slate-600",
};

export function StatusBadge({ children, tone = "slate", className }: { children: ReactNode; tone?: Tone; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em]", toneClasses[tone], className)}>
      {children}
    </span>
  );
}

export function MockBadge({ future = false }: { future?: boolean }) {
  // Demo-hardening spec: admin cards backed by no real endpoint yet must
  // read exactly "DEMO / NOT IMPLEMENTED" so a viewer never mistakes
  // placeholder content for real system state. `future` is kept as a
  // prop (rather than removed) so call sites document their intent even
  // though both branches render identically today.
  void future;
  return <StatusBadge tone="amber">DEMO / NOT IMPLEMENTED</StatusBadge>;
}