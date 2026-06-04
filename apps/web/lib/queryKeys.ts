export const queryKeys = {
  sessions: { all: ["sessions"] as const },
  approvals: { all: (status: string) => ["approvals", status] as const },
  audit: { all: ["audit"] as const },
  kpi: {
    trends: ["kpi", "trends"] as const,
    llmCost: ["kpi", "llm-cost"] as const,
  },
  agents: { registry: ["agents", "registry"] as const },
  jobs: {
    list: (status: string) => ["jobs", status] as const,
    files: ["jobs", "files"] as const,
  },
  usage: {
    steps: ["usage", "steps"] as const,
    llm: ["usage", "llm"] as const,
    llmCalls: ["usage", "llm-calls"] as const,
  },
  settings: { groundTruth: ["settings", "ground-truth"] as const },
  scenarios: { detail: (sessionId: string) => ["scenarios", sessionId] as const },
  recommendations: { detail: (id: string) => ["recommendations", id] as const },
} as const;
