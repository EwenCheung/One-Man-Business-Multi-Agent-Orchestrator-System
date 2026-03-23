import {
  CustomerRow,
  DashboardStat,
  DigestItem,
  InvestorRow,
  PartnerRow,
  PendingApproval,
  SupplierRow,
} from "./types";

export const dashboardStats: DashboardStat[] = [
  {
    title: "Pending approvals",
    value: "12",
    description: "Awaiting owner review",
  },
  {
    title: "Daily conversations",
    value: "28",
    description: "Processed today",
  },
  {
    title: "High-risk flags",
    value: "3",
    description: "Needs immediate review",
  },
  {
    title: "Approved today",
    value: "19",
    description: "Memory / DB changes accepted",
  },
];

export const pendingApprovals: PendingApproval[] = [
  {
    id: "pa-001",
    userId: "cust-001",
    role: "customer",
    proposalType: "memory_update",
    reason: "User repeatedly asked for discount bundles.",
    oldValue: "Prefers affordable products",
    newValue: "Prefers affordable products and bundle discounts",
    riskLevel: "low",
    status: "pending",
  },
  {
    id: "pa-002",
    userId: "sup-011",
    role: "supplier",
    proposalType: "db_update",
    reason: "Supplier mentioned updated stock quantity and lead time.",
    oldValue: "Stock: 180, lead time: 7 days",
    newValue: "Stock: 260, lead time: 5 days",
    riskLevel: "medium",
    status: "pending",
  },
  {
    id: "pa-003",
    userId: "inv-004",
    role: "investor",
    proposalType: "role_flag",
    reason: "Conversation mixed partner and investor signals.",
    oldValue: "Investor",
    newValue: "Investor / Partner review needed",
    riskLevel: "high",
    status: "pending",
  },
];

export const dailyDigest: DigestItem[] = [
  {
    id: "dg-001",
    title: "Supplier stock change detected",
    summary: "A supplier reported increased stock and shorter delivery lead time.",
    category: "Supplier",
    riskLevel: "medium",
    timestamp: "09:20 AM",
  },
  {
    id: "dg-002",
    title: "Customer preference strengthened",
    summary: "A customer consistently showed strong interest in discounted bundles.",
    category: "Customer",
    riskLevel: "low",
    timestamp: "10:45 AM",
  },
  {
    id: "dg-003",
    title: "Ambiguous investor intent",
    summary: "One thread suggests investment interest but also partnership inquiries.",
    category: "Investor",
    riskLevel: "high",
    timestamp: "01:10 PM",
  },
];

export const customers: CustomerRow[] = [
  {
    id: "c-001",
    name: "Customer A",
    preference: "Bulk discounts",
    lastInteraction: "Today",
  },
  {
    id: "c-002",
    name: "Customer B",
    preference: "Premium products",
    lastInteraction: "Yesterday",
  },
];

export const suppliers: SupplierRow[] = [
  {
    id: "s-001",
    company: "Alpha Supply Co",
    supplyPrice: "$18.20",
    stock: "260",
  },
  {
    id: "s-002",
    company: "Beta Wholesale",
    supplyPrice: "$15.90",
    stock: "430",
  },
];

export const investors: InvestorRow[] = [
  {
    id: "i-001",
    product: "Product X",
    roi: "18%",
    dailySales: "42",
  },
  {
    id: "i-002",
    product: "Product Y",
    roi: "24%",
    dailySales: "35",
  },
];

export const partners: PartnerRow[] = [
  {
    id: "p-001",
    name: "Retail Partner SG",
    partnershipType: "Distribution",
    status: "Active",
  },
  {
    id: "p-002",
    name: "Brand Partner ID",
    partnershipType: "Co-marketing",
    status: "Review",
  },
];