import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { Investigation } from "@/hooks/useQueryAI";

interface Store {
  items: Investigation[];
  activeId: string | null;
  add: (i: Investigation) => void;
  setActive: (id: string) => void;
  active: Investigation | null;
}

const Ctx = createContext<Store | undefined>(undefined);

export function InvestigationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Investigation[]>([]);
  const [activeId, setActive] = useState<string | null>(null);
  const add = useCallback((i: Investigation) => {
    setItems((xs) => [i, ...xs].slice(0, 30));
    setActive(i.id);
  }, []);
  const value = useMemo(() => ({ items, activeId, add, setActive, active: items.find((i) => i.id === activeId) ?? items[0] ?? null }), [items, activeId, add]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useInvestigations() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useInvestigations outside provider");
  return c;
}
