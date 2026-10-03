import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  kicker?: string;
  title: ReactNode;
  headerExtra?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
  testid?: string;
}

export function Drawer({ open, onClose, kicker, title, headerExtra, children, footer, width = "w-[min(640px,100vw)]", testid }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" aria-label="Close drawer" data-testid="drawer-backdrop" className="absolute inset-0 bg-[#04060a]/70 backdrop-blur-[2px]" onClick={onClose} />
      <aside data-testid={testid} className={cn("relative flex h-full flex-col border-l border-line bg-panel", width)} style={{ animation: "nwis-rise 220ms cubic-bezier(.2,.7,.2,1) both" }}>
        <header className="flex shrink-0 items-start gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0 flex-1">
            {kicker && <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-signal">{kicker}</div>}
            <div className="mt-1">{title}</div>
            {headerExtra && <div className="mt-2">{headerExtra}</div>}
          </div>
          <button type="button" onClick={onClose} data-testid="drawer-close-btn" className="flex size-7 items-center justify-center border border-line text-dim transition-colors hover:border-faint hover:text-ink">
            <X className="size-3.5" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="shrink-0 border-t border-line px-5 py-3">{footer}</footer>}
      </aside>
    </div>
  );
}
