import { cn } from "@/lib/utils";

const FILL = { signal: "bg-signal", warn: "bg-warn", crit: "bg-crit", dim: "bg-dim", similar: "bg-similar" } as const;

export function Meter({ value, segments = 20, tone = "signal", className, testid }: {
  value: number; segments?: number; tone?: keyof typeof FILL; className?: string; testid?: string;
}) {
  const v = Math.max(0, Math.min(1, value));
  const lit = Math.round(v * segments);
  return (
    <div data-testid={testid} className={cn("flex h-2 gap-[2px]", className)} role="meter" aria-valuenow={v} aria-valuemin={0} aria-valuemax={1}>
      {Array.from({ length: segments }).map((_, i) => (
        <span key={i} className={cn("flex-1 transition-colors duration-300", i < lit ? FILL[tone] : "bg-raised")} />
      ))}
    </div>
  );
}

export function ThinBar({ value, tone = "signal", className }: { value: number; tone?: keyof typeof FILL; className?: string }) {
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className={cn("h-1 w-full bg-raised", className)}>
      <div className={cn("h-full transition-[width] duration-500", FILL[tone])} style={{ width: `${v * 100}%` }} />
    </div>
  );
}
