import { request, qs } from "./client";
import type {
  Snapshot,
  InstanceListResponse,
  RegisterInstanceRequest,
  RegisterInstanceResponse,
  TestInstanceResponse,
  AgentJobsSnapshot,
  DatabaseStatus,
  BlockingSnapshot,
  WaitStats,
  AiExplainRequest,
  AiExplainResponse,
  AiSuggestRequest,
  AiSuggestResponse,
  AiAskRequest,
  AiAskResponse,
  ConditionsResponse,
  RunbookListResponse,
  RunbookUploadResponse,
  GapReport,
  IncidentReportResponse,
} from "../types/api";

export const IS_DEMO = import.meta.env.VITE_DEMO === "true";

const liveApi = {
  getSnapshot: (instance?: string, fresh = false) =>
    request<Snapshot>(
      `/health/snapshot${qs({ instance, ...(fresh ? { fresh: "true" } : {}) })}`
    ),

  getInstances: () => request<InstanceListResponse>("/instances/"),

  registerInstance: (body: RegisterInstanceRequest) =>
    request<RegisterInstanceResponse>("/instances/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  testInstance: (name: string) =>
    request<TestInstanceResponse>(`/instances/${encodeURIComponent(name)}/test`),

  getJobs: (instance?: string) =>
    request<AgentJobsSnapshot>(`/monitoring/jobs${qs({ instance })}`),

  getDatabases: (instance?: string) =>
    request<DatabaseStatus>(`/monitoring/databases${qs({ instance })}`),

  getBlocking: (instance?: string) =>
    request<BlockingSnapshot>(`/monitoring/blocking${qs({ instance })}`),

  getWaits: (instance?: string) =>
    request<WaitStats>(`/monitoring/waits${qs({ instance })}`),

  aiExplain: (body: AiExplainRequest) =>
    request<AiExplainResponse>("/ai/explain", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  aiSuggest: (body: AiSuggestRequest) =>
    request<AiSuggestResponse>("/ai/suggest", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  aiAsk: (body: AiAskRequest) =>
    request<AiAskResponse>("/ai/ask", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Runbook automation ------------------------------------------------------

  getConditions: (instance?: string) =>
    request<ConditionsResponse>(`/incidents/conditions${qs({ instance })}`),

  draftIncidentReport: (instance?: string) =>
    request<IncidentReportResponse>("/incidents/report", {
      method: "POST",
      body: JSON.stringify({ instance: instance ?? null }),
    }),

  getRunbooks: () => request<RunbookListResponse>("/runbooks/"),

  uploadRunbook: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    // No Content-Type header: the browser sets the multipart boundary.
    return request<RunbookUploadResponse>("/runbooks/upload", {
      method: "POST",
      body: form,
      headers: {},
    });
  },

  deleteRunbook: (docId: string) =>
    request<{ removed: string }>(`/runbooks/${encodeURIComponent(docId)}`, {
      method: "DELETE",
    }),

  getRunbookGaps: (days = 90) =>
    request<GapReport>(`/runbooks/gaps${qs({ days: String(days) })}`),
};

// In demo builds (VITE_DEMO=true) every call is served from local fixtures so
// the dashboard can run as a static site with no backend.
import { demoApi } from "./demo";

export const api: typeof liveApi = IS_DEMO ? demoApi : liveApi;
