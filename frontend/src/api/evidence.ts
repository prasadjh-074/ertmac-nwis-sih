import type { NwisCapability } from "./nwis";

/** UI state for the drawer before a backend evidence schema is confirmed. */
export interface EvidenceViewState {
  status: "unavailable";
  title: string;
  subtitle: string;
  endpoint: string;
  message: string;
  cards: readonly { label: string; value: string }[];
}

export function unavailableEvidence(capability: NwisCapability): EvidenceViewState {
  return {
    status: "unavailable",
    title: "Why this alert?",
    subtitle: "Evidence drawer is waiting for the confirmed risk contract.",
    endpoint: `${capability.method} ${capability.endpoint}`,
    message: "No risk alert record was returned. The running API does not expose alert, event, score, or provenance fields yet.",
    cards: [
      { label: "Contributing evidence", value: "Waiting for backend response" },
      { label: "Methodology", value: "Waiting for backend response" },
      { label: "Historical events", value: "No records returned" },
      { label: "Limitations", value: "Decision support only" },
    ],
  };
}