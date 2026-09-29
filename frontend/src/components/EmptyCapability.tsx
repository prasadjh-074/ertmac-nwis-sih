import { CircleDashed, type LucideIcon } from "@/lib/lucide-react";
import { MockBadge } from "./StatusBadge";

export function EmptyCapability({
  title,
  description,
  endpoint,
  icon: Icon = CircleDashed,
  future = true,
}: {
  title: string;
  description: string;
  endpoint: string;
  icon?: LucideIcon;
  future?: boolean;
}) {
  return (
    <div data-testid={`capability-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} className="flex min-h-36 flex-col items-center justify-center border border-dashed border-slate-300 bg-slate-50/70 px-5 py-7 text-center">
      <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm ring-1 ring-slate-200">
        <Icon size={18} aria-hidden="true" />
      </div>
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-semibold text-slate-800" data-testid={`${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-title`}>{title}</p>
        <MockBadge future={future} />
      </div>
      <p className="max-w-md text-xs leading-relaxed text-slate-500" data-testid={`${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-description`}>{description}</p>
      <code className="mt-3 font-mono text-[10px] text-slate-400" data-testid={`${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-endpoint`}>{endpoint}</code>
    </div>
  );
}