export const queryKeys = {
  instances: ["instances"] as const,
  snapshot: (instance: string | undefined) => ["snapshot", instance] as const,
  jobs: (instance: string | undefined) => ["jobs", instance] as const,
  databases: (instance: string | undefined) => ["databases", instance] as const,
  blocking: (instance: string | undefined) => ["blocking", instance] as const,
  waits: (instance: string | undefined) => ["waits", instance] as const,
  conditions: (instance: string | undefined) => ["conditions", instance] as const,
  runbooks: ["runbooks"] as const,
  runbookGaps: (days: number) => ["runbook-gaps", days] as const,
};
