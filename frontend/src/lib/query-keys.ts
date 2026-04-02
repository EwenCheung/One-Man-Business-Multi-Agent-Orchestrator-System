export const queryKeys = {
  ownerDashboard: {
    all: ["owner-dashboard"] as const,
    summary: () => ["owner-dashboard", "summary"] as const,
  },
  approvals: {
    all: ["approvals"] as const,
    pending: () => ["approvals", "pending"] as const,
  },
  dailyDigest: {
    all: ["daily-digest"] as const,
    list: () => ["daily-digest", "list"] as const,
  },
  memory: {
    all: ["memory"] as const,
    overview: () => ["memory", "overview"] as const,
  },
  stakeholders: {
    all: ["stakeholders"] as const,
    byRole: (role: string) => ["stakeholders", role] as const,
  },
};
