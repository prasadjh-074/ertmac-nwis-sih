import { useWorkspace } from "@/state/WorkspaceContext";
import { WhyDrawer } from "@/features/risk/WhyDrawer";
import { EventDrawer } from "@/features/events/EventDrawer";
import { DocumentDrawer } from "@/features/documents/DocumentDrawer";

export function DrawerHost() {
  const { drawer } = useWorkspace();
  if (!drawer) return null;
  switch (drawer.kind) {
    case "alert":
      return <WhyDrawer key={`a-${drawer.alert.alert_id}`} alert={drawer.alert} />;
    case "risk":
      return <WhyDrawer key={`r-${drawer.riskType}`} riskType={drawer.riskType} />;
    case "event":
      return <EventDrawer event={drawer.event} correlation={drawer.correlation} />;
    case "document":
      return <DocumentDrawer documentId={drawer.documentId} chunk={drawer.chunk} />;
  }
}
