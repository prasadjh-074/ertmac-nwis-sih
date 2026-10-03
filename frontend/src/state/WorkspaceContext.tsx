import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { Alert, CorrelatedEvent, DocumentChunk, DrillingEvent, WellRef } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { logSessionEvent } from "@/lib/sessionLog";

export type DrawerState =
  | { kind: "alert"; alert: Alert }
  | { kind: "risk"; riskType: string }
  | { kind: "event"; event: DrillingEvent; correlation?: CorrelatedEvent }
  | { kind: "document"; documentId: string; chunk?: DocumentChunk };

export interface Highlight {
  refs: WellRef[];
  label: string;
}

interface WorkspaceValue {
  currentWell: WellRef | null;
  setCurrentWell: (ref: WellRef) => void;
  depthOverride: number | null;
  setDepthOverride: (d: number | null) => void;
  formationOverride: string;
  setFormationOverride: (f: string) => void;
  radiusKm: number;
  setRadiusKm: (r: number) => void;
  selection: WellRef[] | null;
  selectWells: (refs: WellRef[] | null) => void;
  highlight: Highlight | null;
  setHighlight: (h: Highlight | null) => void;
  drawer: DrawerState | null;
  openDrawer: (d: DrawerState) => void;
  closeDrawer: () => void;
  aiDraft: string | null;
  setAiDraft: (q: string | null) => void;
  navCollapsed: boolean;
  setNavCollapsed: (v: boolean) => void;
}

const WorkspaceContext = createContext<WorkspaceValue | undefined>(undefined);
const CURRENT_KEY = "nwis-current-well";

function readCurrent(): WellRef | null {
  try {
    const v = JSON.parse(window.localStorage.getItem(CURRENT_KEY) ?? "null");
    return v && typeof v.dataset === "string" && typeof v.well_id === "string" ? v : null;
  } catch {
    return null;
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [currentWell, setCurrent] = useState<WellRef | null>(readCurrent);
  const [depthOverride, setDepthOverride] = useState<number | null>(null);
  const [formationOverride, setFormationOverride] = useState("");
  const [radiusKm, setRadiusKm] = useState(50);
  const [selection, selectWells] = useState<WellRef[] | null>(null);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [aiDraft, setAiDraft] = useState<string | null>(null);
  const [navCollapsed, setNavCollapsed] = useState(false);

  const setCurrentWell = useCallback(
    (ref: WellRef) => {
      setCurrent(ref);
      window.localStorage.setItem(CURRENT_KEY, JSON.stringify(ref));
      setDepthOverride(null);
      setFormationOverride("");
      setHighlight(null);
      selectWells(null);
      if (user) logSessionEvent(user.employeeId, "Set current well", `${ref.dataset}:${ref.well_id}`, "Allowed");
    },
    [user],
  );

  const value = useMemo<WorkspaceValue>(
    () => ({
      currentWell, setCurrentWell, depthOverride, setDepthOverride, formationOverride, setFormationOverride,
      radiusKm, setRadiusKm, selection, selectWells, highlight, setHighlight, drawer,
      openDrawer: setDrawer, closeDrawer: () => setDrawer(null), aiDraft, setAiDraft, navCollapsed, setNavCollapsed,
    }),
    [currentWell, setCurrentWell, depthOverride, formationOverride, radiusKm, selection, highlight, drawer, aiDraft, navCollapsed],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}
