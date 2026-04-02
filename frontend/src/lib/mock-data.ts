export const customers = [
  {
    id: "cust_001",
    name: "Avery Tan",
    email: "avery@example.com",
    company: "Northstar Retail",
    status: "active",
  },
  {
    id: "cust_002",
    name: "Jordan Lim",
    email: "jordan@example.com",
    company: "Brightline Goods",
    status: "pending",
  },
];

export const pendingApprovals = [
  {
    id: "approval_001",
    title: "Memory update requires approval",
    sender: "Memory Agent",
    preview: "Store a new customer preference about bulk discounts.",
    proposal_type: "memory-update",
    risk_level: "medium",
    status: "pending",
    proposal_id: "proposal_001",
  },
];

export const dailyDigest = [
  {
    id: "digest_001",
    title: "Daily digest ready",
    risk: "low",
    summary: "3 approvals pending and customer activity is within normal range.",
  },
];
