import type { ReactNode } from "react";

export type TableColumn<T extends Record<string, unknown>> = {
  key: keyof T | string;
  label: string;
  render?: (value: unknown, row: T) => ReactNode;
};

export type CustomerRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  status: string | null;
};

export type SupplierRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  category: string | null;
  contract_notes?: string | null;
  status: string | null;
};

export type InvestorRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  focus: string | null;
  notes?: string | null;
  status: string | null;
};

export type PartnerRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  partner_type: string | null;
  notes?: string | null;
  status: string | null;
};

export type StakeholderRole = "customers" | "suppliers" | "investors" | "partners";

export type StakeholderRow =
  | ({ role: "customers" } & CustomerRow)
  | ({ role: "suppliers" } & SupplierRow)
  | ({ role: "investors" } & InvestorRow)
  | ({ role: "partners" } & PartnerRow);

export type StakeholderInput = {
  name: string;
  email?: string | null;
  phone?: string | null;
  status?: string | null;
  company?: string | null;
  preference?: string | null;
  notes?: string | null;
  category?: string | null;
  contract_notes?: string | null;
  focus?: string | null;
  partner_type?: string | null;
};

export type StakeholderSwitchInput = {
  sourceRole: StakeholderRole;
  sourceId: string;
  targetRole: StakeholderRole;
};

export type ProductRow = {
  id: string;
  name: string;
  description: string | null;
  selling_price: number | null;
  cost_price: number | null;
  stock_number: number | null;
  product_link: string | null;
  category: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProductInput = {
  name: string;
  description?: string | null;
  selling_price?: number | null;
  cost_price?: number | null;
  stock_number?: number | null;
  product_link?: string | null;
  category?: string | null;
};

export type ApprovalItem = {
  id: string;
  title: string;
  sender: string | null;
  preview: string | null;
  proposal_type: string | null;
  risk_level: string | null;
  status?: string | null;
  proposal_id?: string | null;
  held_reply_id?: string | null;
  created_at?: string | null;
};

export type DashboardStat = {
  title: string;
  value: string;
  description: string;
};

export type DailyDigestItem = {
  id: string;
  title: string;
  summary: string | null;
  risk: string | null;
  created_at?: string | null;
};

export type DailyDigestInput = {
  title: string;
  summary: string;
  risk: string;
};

export type OwnerMemoryRule = {
  id: string;
  role: string;
  category: string;
  content: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type EntityMemory = {
  id: string;
  entity_role: string;
  entity_id: string;
  memory_type: string;
  content: string;
  summary: string | null;
  importance: number | null;
  updated_at?: string | null;
};

export type DashboardPayload = {
  stats: DashboardStat[];
  pendingApprovals: ApprovalItem[];
  dailyDigest: DailyDigestItem[];
  memoryQueue: ApprovalItem[];
};

export type MemoryOverviewPayload = {
  pendingUpdates: ApprovalItem[];
  ownerRules: OwnerMemoryRule[];
  entityMemories: EntityMemory[];
  dailyDigest: DailyDigestItem[];
};
