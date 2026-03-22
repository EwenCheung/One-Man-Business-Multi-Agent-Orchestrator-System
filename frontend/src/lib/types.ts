export type Role = "customer" | "supplier" | "investor" | "partner";

export type DashboardStat = {
  title: string;
  value: string;
  description: string;
};

export type PendingApproval = {
  id: string;
  userId: string;
  role: Role;
  proposalType: "memory_update" | "db_update" | "role_flag";
  reason: string;
  oldValue: string;
  newValue: string;
  riskLevel: "low" | "medium" | "high";
  status: "pending" | "approved" | "rejected";
};

export type DigestItem = {
  id: string;
  title: string;
  summary: string;
  category: string;
  riskLevel: "low" | "medium" | "high";
  timestamp: string;
};

export type TableColumn<T> = {
  key: keyof T;
  label: string;
};

export type CustomerRow = {
  id: string;
  name: string;
  preference: string;
  lastInteraction: string;
};

export type SupplierRow = {
  id: string;
  company: string;
  supplyPrice: string;
  stock: string;
};

export type InvestorRow = {
  id: string;
  product: string;
  roi: string;
  dailySales: string;
};

export type PartnerRow = {
  id: string;
  name: string;
  partnershipType: string;
  status: string;
};