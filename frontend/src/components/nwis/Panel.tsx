import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PanelProps {
  code?: string;
  title: string;
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  testid?: string;
}

export function Panel({ code, title, meta, actions, children, className, bodyClassName, testid }: PanelProps) {
  return (
    <section data-testid={testid} className={cn("flex min-h-0 min-w-0 flex-col border border-line bg-panel", className)}>
      <header className="flex h-8 shrink-0 items-center gap-3 border-b border-line px-3">
        {code && <span className="font-mono text-[10px] text-faint">{code}</span>}
        <h2 className="font-semicond truncate text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">{title}</h2>
        {meta && <div className="truncate font-mono text-[10px] text-faint">{meta}</div>}
        <div className="ml-auto flex items-center gap-1.5">{actions}</div>
      </header>
      <div className={cn("min-h-0 flex-1 overflow-auto", bodyClassName)}>{children}</div>
    </section>
  );
}

export function SectionLabel({ index, children, className }: { index?: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      {index && <span className="font-mono text-[10px] text-signal">{index}</span>}
      <span className="label">{children}</span>
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}

export function KV({ label, value, mono = true, testid }: { label: string; value: ReactNode; mono?: boolean; testid?: string }) {
  return (
    <div className="min-w-0">
      <div className="label">{label}</div>
      <div data-testid={testid} className={cn("mt-0.5 truncate text-[13px] text-ink", mono && "font-mono tnum")}>{value}</div>
    </div>
  );
}

export function ToolButton({ children, onClick, active, disabled, testid, title, className }: {
  children: ReactNode; onClick?: () => void; active?: boolean; disabled?: boolean; testid?: string; title?: string; className?: string;
}) {
  return (
    <button
      type="button"
      title={title}
      data-testid={testid}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex h-7 items-center gap-1.5 border px-2.5 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40",
        active ? "border-signal/60 bg-signal-deep text-signal" : "border-line bg-panel2 text-dim hover:border-faint hover:text-ink",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function PrimaryButton({ children, onClick, disabled, testid, type = "button", className }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; testid?: string; type?: "button" | "submit"; className?: string;
}) {
  return (
    <button
      type={type}
      data-testid={testid}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex h-8 items-center justify-center gap-2 bg-signal px-3.5 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-[#061014] transition-[background-color,transform] duration-150 hover:bg-[#5ad6e5] active:translate-y-px disabled:cursor-not-allowed disabled:bg-raised disabled:text-faint",
        className,
      )}
    >
      {children}
    </button>
  );
}
