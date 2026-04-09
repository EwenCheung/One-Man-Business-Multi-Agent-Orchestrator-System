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
  preference: string | null;
  notes: string | null;
  telegram_user_id: string | null;
  telegram_username: string | null;
  telegram_chat_id: string | null;
  last_contact: string | null;
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
  telegram_username?: string | null;
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

export type OrderRow = {
  id: string;
  customer_id: string;
  product_id: string;
  quantity: number;
  total_price: number | null;
  order_date: string | null;
  status: string | null;
  channel: string | null;
  created_at?: string | null;
  customer_name: string | null;
  customer_email: string | null;
  product_name: string | null;
  message_thread_id: string | null;
};

export type OrderDetail = OrderRow & {
  customer_phone: string | null;
  customer_company: string | null;
  customer_preference: string | null;
  customer_notes: string | null;
  product_description: string | null;
  product_category: string | null;
  product_link: string | null;
  selling_price: number | null;
  cost_price: number | null;
  stock_number: number | null;
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
  contextDetails?: ApprovalContextDetails | null;
};

export type ApprovalContextDetails = 
  | {
      type: "reply";
      explanation: string;
      approvalReason: string;
      conversationLinkThreadId: string | null;
      heldReply: {
        thread_id: string | null;
        sender_id: string | null;
        sender_name: string | null;
        sender_role: string | null;
        reply_text: string;
        risk_flags: string[] | null;
      };
      threadContext: {
        sender_external_id: string | null;
        sender_name: string | null;
        sender_role: string | null;
        sender_channel: string | null;
      } | null;
      recentMessages: Array<{
        direction: string;
        content: string;
        sender_name: string | null;
        created_at: string | null;
      }>;
    }
  | {
      type: "memory";
      explanation: string;
      approvalReason: string;
      conversationLinkThreadId: string | null;
      proposal: {
        target_table: string;
        target_id: string | null;
        proposed_content: unknown;
        reason: string | null;
        risk_level: string | null;
      };
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

export type DailyDigestActivityItem = {
  title: string;
  detail: string;
};

export type DailyDigestMonthlyStat = {
  month: string;
  orders: number;
  paidSales: number;
};

export type DailyDigestPayload = {
  items: DailyDigestItem[];
  metrics: {
    contactsToday: number;
    newOrdersToday: number;
    paidSalesToday: number;
    memoryUpdatesToday: number;
  };
  monthly: DailyDigestMonthlyStat[];
  activities: DailyDigestActivityItem[];
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

export type OwnerProfile = {
  id: string;
  full_name: string | null;
  business_name: string | null;
  business_description: string | null;
  business_industry: string | null;
  business_timezone: string | null;
  preferred_language: string | null;
  default_reply_tone: string | null;
  sender_summary_threshold: number | null;
  notifications_email: string | null;
  notifications_enabled: boolean | null;
  memory_context: string | null;
  soul_context: string | null;
  rule_context: string | null;
  telegram_bot_token: string | null;
  telegram_webhook_secret: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type OwnerProfileInput = Partial<
  Pick<
    OwnerProfile,
    | "full_name"
    | "business_name"
    | "business_description"
    | "business_industry"
    | "business_timezone"
    | "preferred_language"
    | "default_reply_tone"
    | "sender_summary_threshold"
    | "notifications_email"
    | "notifications_enabled"
    | "memory_context"
    | "soul_context"
    | "rule_context"
    | "telegram_bot_token"
    | "telegram_webhook_secret"
  >
>;

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
  dailyDigest: DailyDigestPayload;
  memoryQueue: ApprovalItem[];
};

export type MemoryOverviewPayload = {
  pendingUpdates: ApprovalItem[];
  ownerRules: OwnerMemoryRule[];
  entityMemories: EntityMemory[];
  dailyDigest: DailyDigestItem[];
  ownerProfile: OwnerProfile | null;
};

export type MessageSenderRole = "customer" | "supplier" | "partner" | "investor";

export type ThreadSender = {
  external_id: string | null;
  name: string | null;
  role: string | null;
  channel: string | null;
};

export type MessageThreadPreview = {
  thread_id: string;
  thread_type: string;
  sender: ThreadSender;
  title: string | null;
  preview: string | null;
  latest_direction: string | null;
  last_message_at: string | null;
  message_count: number;
  unread_count: null;
  unread_tracking: string;
  pending_summary_count: number;
  sender_summary_available: boolean;
  last_summarized_at: string | null;
  updated_at: string | null;
};

export type MessageThreadsResponse = {
  threads: MessageThreadPreview[];
  filters: {
    sender_roles: string[];
  };
  status: string;
};

export type MessageInThread = {
  id: string;
  direction: string;
  content: string;
  sender_id: string | null;
  sender_name: string | null;
  sender_role: string | null;
  created_at: string | null;
};

export type ThreadDetail = {
  thread_id: string;
  thread_type: string;
  title: string | null;
  last_message_at: string | null;
  sender: ThreadSender;
};

export type SenderSummary = {
  summary: string | null;
  pending_summary_count: number;
  last_message_at: string | null;
  last_summarized_at: string | null;
};

export type MessageThreadDetailResponse = {
  thread: ThreadDetail;
  sender_summary: SenderSummary;
  messages: MessageInThread[];
  status: string;
};

export type OwnerChatThread = {
  thread_id: string;
  title: string | null;
  last_message_at: string | null;
  message_count: number;
};

export type OwnerChatThreadsResponse = {
  threads: OwnerChatThread[];
  status: string;
};

export type OwnerChatThreadDetailResponse = {
  thread: ThreadDetail;
  messages: MessageInThread[];
  status: string;
};

export type MyChatThreadResponse = {
  thread: ThreadDetail | null;
  messages: MessageInThread[];
  status: string;
};
