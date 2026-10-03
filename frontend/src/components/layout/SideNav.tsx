import { NavLink } from "react-router-dom";
import { PanelLeftClose, PanelLeftOpen, type LucideIcon } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import type { Permission } from "@/auth/permissions";
import { cn } from "@/lib/utils";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  permission: Permission;
  code: string;
}

export function SideNav({ title, items, collapsed, onToggle, footer }: { title: string; items: NavItem[]; collapsed: boolean; onToggle: () => void; footer?: React.ReactNode }) {
  const { can } = useAuth();
  return (
    <nav data-testid="side-nav" className={cn("flex shrink-0 flex-col border-r border-line bg-bg transition-[width] duration-200", collapsed ? "w-[52px]" : "w-[200px]")}>
      <div className="flex h-9 items-center justify-between border-b border-line px-3">
        {!collapsed && <span className="label">{title}</span>}
        <button type="button" data-testid="nav-collapse-toggle" onClick={onToggle} className="text-faint transition-colors hover:text-ink" title={collapsed ? "Expand navigation" : "Collapse navigation"}>
          {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
        </button>
      </div>
      <ul className="flex-1 py-1.5">
        {items.filter((i) => can(i.permission)).map((i) => (
          <li key={i.to}>
            <NavLink
              to={i.to}
              end
              data-testid={`nav-${i.label.toLowerCase().replace(/[^a-z]+/g, "-")}`}
              title={i.label}
              className={({ isActive }) => cn(
                "group relative flex h-8 items-center gap-2.5 px-3 text-[12px] transition-colors",
                isActive ? "bg-panel text-ink" : "text-dim hover:bg-panel/60 hover:text-ink",
              )}
            >
              {({ isActive }) => (
                <>
                  <span className={cn("absolute inset-y-1 left-0 w-[2px]", isActive ? "bg-signal" : "bg-transparent")} />
                  <i.icon className={cn("size-4 shrink-0", isActive ? "text-signal" : "text-faint group-hover:text-dim")} strokeWidth={1.5} />
                  {!collapsed && <span className="flex-1 truncate">{i.label}</span>}
                  {!collapsed && <span className="font-mono text-[9px] text-faint">{i.code}</span>}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
      {!collapsed && footer && <div className="border-t border-line px-3 py-2.5">{footer}</div>}
    </nav>
  );
}
