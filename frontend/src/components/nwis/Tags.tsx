import type { ReactNode } from "react";
import { AlertOctagon, AlertTriangle, CircleDot, Info, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "crit" | "warn" | "ok" | "info" | "neutral";

const TONE: Record<Tone, string> = {
  crit: "text-crit border-crit/40 bg-crit-deep/60",
  warn: "text-warn border-warn/40 bg-warn-deep/60",
  ok: "text-ok border-ok/40 bg-ok-deep/60",
  info: "text-signal border-signal/40 bg-signal-deep/60",
  neutral: "text-dim border-line bg-panel2",
};

export const toneForLevel = (level: string): Tone => {
  const l = level.toLowerCase();
  if (l === "critical" || l === "high") return "crit";
  if (l === "medium" || l === "warning") return "warn";
  if (l === "low" || l === "info") return "neutral";
  return "neutral";
};

const iconFor = (level: string) => {
  const l = level.toLowerCase();
  if (l === "critical") return AlertOctagon;
  if (l === "high") return AlertTriangle;
  if (l === "medium" || l === "warning") return AlertTriangle;
  if (l === "info") return Info;
  if (l === "low") return Minus;
  return CircleDot;
};

export function LevelTag({ level, className, testid }: { level: string; className?: string; testid?: string }) {
  const Icon = iconFor(level);
  return (
    <span data-testid={testid} className={cn("inline-flex h-5 shrink-0 items-center gap-1 border px-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em]", TONE[toneForLevel(level)], className)}>
      <Icon className="size-3" strokeWidth={2} />
      {level}
    </span>
  );
}

export function Tag({ children, tone = "neutral", className, testid }: { children: ReactNode; tone?: Tone; className?: string; testid?: string }) {
  return (
    <span data-testid={testid} className={cn("inline-flex h-5 shrink-0 items-center gap-1 border px-1.5 font-mono text-[10px] uppercase tracking-[0.1em]", TONE[tone], className)}>
      {children}
    </span>
  );
}

const DATA_TAGS = {
  live: { text: "Backend data", tone: "ok" },
  mock: { text: "Mock · Backend endpoint pending", tone: "warn" },
  demo: { text: "Demo data", tone: "warn" },
  pending: { text: "Backend endpoint pending", tone: "warn" },
  local: { text: "Local browser record", tone: "info" },
  simulated: { text: "Demo / simulated state", tone: "warn" },
} as const;

export function DataTag({ kind, className }: { kind: keyof typeof DATA_TAGS; className?: string }) {
  const t = DATA_TAGS[kind];
  return (
    <Tag tone={t.tone} className={cn("border-dashed", className)} testid={`data-tag-${kind}`}>
      {t.text}
    </Tag>
  );
}

export function StatusDot({ state }: { state: "ok" | "warn" | "crit" | "unknown" }) {
  const c = { ok: "bg-ok", warn: "bg-warn", crit: "bg-crit", unknown: "bg-faint" }[state];
  return (
    <span className="relative inline-flex size-2 shrink-0">
      {state === "ok" && <span className={cn("absolute inset-0 rounded-full opacity-60", c)} style={{ animation: "nwis-ping 2.4s ease-out infinite" }} />}
      <span className={cn("relative inline-flex size-2 rounded-full", c)} />
    </span>
  );
}
