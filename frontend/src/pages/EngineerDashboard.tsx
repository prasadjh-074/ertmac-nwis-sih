import { Route, Routes } from "react-router-dom";
import { Bell, Bot, FileSearch, GitCompareArrows, History, LayoutDashboard, Map, Radar, ShieldAlert } from "lucide-react";
import { RequirePermission } from "@/auth/RoleGuard";
import { WorkspaceProvider, useWorkspace } from "@/state/WorkspaceContext";
import { InvestigationProvider } from "@/features/ai/InvestigationStore";
import { TopBar } from "@/components/layout/TopBar";
import { SideNav, type NavItem } from "@/components/layout/SideNav";
import { DrawerHost } from "@/components/layout/DrawerHost";
import { CurrentWellBar } from "@/features/wells/CurrentWellBar";
import WorkstationPage from "./engineer/WorkstationPage";
import MapPage from "./engineer/MapPage";
import { NearbyPage, SimilarPage } from "./engineer/OffsetPages";
import EventsPage from "./engineer/EventsPage";
import { AlertsPage, RiskPage } from "./engineer/RiskPages";
import AssistantPage from "./engineer/AssistantPage";
import DocumentsPage from "./engineer/DocumentsPage";

const NAV: NavItem[] = [
  { to: "/engineer", label: "Overview", icon: LayoutDashboard, permission: "VIEW_WELLS", code: "00" },
  { to: "/engineer/map", label: "Well Map", icon: Map, permission: "VIEW_WELLS", code: "01" },
  { to: "/engineer/nearby", label: "Nearby Wells", icon: Radar, permission: "VIEW_NEARBY_WELLS", code: "02" },
  { to: "/engineer/similar", label: "Similar Wells", icon: GitCompareArrows, permission: "VIEW_SIMILAR_WELLS", code: "03" },
  { to: "/engineer/events", label: "Events", icon: History, permission: "VIEW_EVENTS", code: "04" },
  { to: "/engineer/risk", label: "Risk", icon: ShieldAlert, permission: "VIEW_RISK", code: "05" },
  { to: "/engineer/alerts", label: "Alerts", icon: Bell, permission: "VIEW_ALERTS", code: "06" },
  { to: "/engineer/assistant", label: "AI Assistant", icon: Bot, permission: "USE_AI_QUERY", code: "07" },
  { to: "/engineer/documents", label: "Documents", icon: FileSearch, permission: "VIEW_DOCUMENTS", code: "08" },
];

function Shell() {
  const { navCollapsed, setNavCollapsed } = useWorkspace();
  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="engineer-app">
      <TopBar scope="Authorized operational data" scopeTone="signal" />
      <div className="flex min-h-0 flex-1">
        <SideNav
          title="Workspace"
          items={NAV}
          collapsed={navCollapsed}
          onToggle={() => setNavCollapsed(!navCollapsed)}
          footer={<p className="font-mono text-[9px] leading-relaxed text-faint">Decision support only. Scores are rule-based evidence indicators, not probabilities.</p>}
        />
        <main className="flex min-w-0 flex-1 flex-col">
          <CurrentWellBar />
          <div className="min-h-0 flex-1 overflow-auto">
            <Routes>
              <Route index element={<WorkstationPage />} />
              <Route path="map" element={<RequirePermission permission="VIEW_WELLS"><MapPage /></RequirePermission>} />
              <Route path="nearby" element={<RequirePermission permission="VIEW_NEARBY_WELLS"><NearbyPage /></RequirePermission>} />
              <Route path="similar" element={<RequirePermission permission="VIEW_SIMILAR_WELLS"><SimilarPage /></RequirePermission>} />
              <Route path="events" element={<RequirePermission permission="VIEW_EVENTS"><EventsPage /></RequirePermission>} />
              <Route path="risk" element={<RequirePermission permission="VIEW_RISK"><RiskPage /></RequirePermission>} />
              <Route path="alerts" element={<RequirePermission permission="VIEW_ALERTS"><AlertsPage /></RequirePermission>} />
              <Route path="assistant" element={<RequirePermission permission="USE_AI_QUERY"><AssistantPage /></RequirePermission>} />
              <Route path="documents" element={<RequirePermission permission="VIEW_DOCUMENTS"><DocumentsPage /></RequirePermission>} />
              <Route path="*" element={<RequirePermission permission="MANAGE_USERS" />} />
            </Routes>
          </div>
        </main>
      </div>
      <DrawerHost />
    </div>
  );
}

export default function EngineerDashboard() {
  return (
    <WorkspaceProvider>
      <InvestigationProvider>
        <Shell />
      </InvestigationProvider>
    </WorkspaceProvider>
  );
}
