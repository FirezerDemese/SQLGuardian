// Demo-mode API: same surface as the real client, backed by fixtures.
// Enabled when the bundle is built with VITE_DEMO=true — lets the dashboard
// run as a fully static site (GitHub Pages) with no SQL Server behind it.
import type { api as realApi } from "./endpoints";
import {
  DEMO_INSTANCES,
  demoSnapshot,
  demoAiExplain,
  demoAiSuggest,
  demoAiAsk,
} from "./demoData";
import {
  demoConditions,
  demoGapReport,
  demoIncidentReport,
  demoRunbookList,
} from "./demoRunbooks";

const registered = [...DEMO_INSTANCES];

const delay = (min = 220, max = 550) =>
  new Promise<void>((resolve) =>
    setTimeout(resolve, min + Math.random() * (max - min))
  );

// AI endpoints get a longer "thinking" pause so the replay feels real
const aiDelay = () => delay(900, 1900);

export const demoApi: typeof realApi = {
  getSnapshot: async (instance) => {
    await delay();
    return demoSnapshot(instance ?? registered[0]);
  },

  getInstances: async () => {
    await delay(80, 200);
    return { instances: [...registered] };
  },

  registerInstance: async (body) => {
    await delay(600, 1200);
    if (!registered.includes(body.name)) registered.push(body.name);
    return { status: "registered", instance: body.name };
  },

  testInstance: async (name) => {
    await delay(500, 1100);
    return {
      status: "connected",
      instance: name,
      server_name: name.toUpperCase(),
      version: "Microsoft SQL Server 2022 (RTM-CU15) - 16.0.4145.4 (X64)",
    };
  },

  getJobs: async (instance) => {
    await delay();
    return demoSnapshot(instance ?? registered[0]).agent_jobs;
  },

  getDatabases: async (instance) => {
    await delay();
    return demoSnapshot(instance ?? registered[0]).database_status;
  },

  getBlocking: async (instance) => {
    await delay();
    return demoSnapshot(instance ?? registered[0]).blocking;
  },

  getWaits: async (instance) => {
    await delay();
    return demoSnapshot(instance ?? registered[0]).wait_stats;
  },

  aiExplain: async () => {
    await aiDelay();
    return demoAiExplain(currentInstanceFromUrl());
  },

  aiSuggest: async () => {
    await aiDelay();
    return demoAiSuggest(currentInstanceFromUrl());
  },

  aiAsk: async (body) => {
    await aiDelay();
    return demoAiAsk(body.question, currentInstanceFromUrl());
  },

  // Runbook automation ------------------------------------------------------

  getConditions: async (instance) => {
    await delay();
    return demoConditions(instance ?? currentInstanceFromUrl());
  },

  draftIncidentReport: async (instance) => {
    await aiDelay();
    return demoIncidentReport(instance ?? currentInstanceFromUrl());
  },

  getRunbooks: async () => {
    await delay();
    return demoRunbookList;
  },

  // Ingestion writes to a corpus on disk, which a static build does not have.
  // Say so rather than faking a success the demo cannot honour.
  uploadRunbook: async () => {
    await delay();
    throw new Error(
      "Runbook upload needs the SQLGuardian backend. This static demo ships a pre-loaded corpus."
    );
  },

  deleteRunbook: async () => {
    await delay();
    throw new Error("Runbook removal needs the SQLGuardian backend.");
  },

  getRunbookGaps: async () => {
    await delay();
    return demoGapReport;
  },
};

// The AI endpoints don't take an instance parameter (the real API targets the
// default instance); in demo mode we infer it from the route so each
// instance's AI Brain tells its own story.
function currentInstanceFromUrl(): string {
  const match = window.location.pathname.match(/instance\/([^/]+)/);
  return match ? decodeURIComponent(match[1]) : "primary";
}
