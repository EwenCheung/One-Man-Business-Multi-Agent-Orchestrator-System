-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "vector" WITH SCHEMA public;

-- ==========================================
-- LEVEL 0: Core Tables (No internal FKs)
-- ==========================================

CREATE TABLE public.profiles (
  id uuid NOT NULL,
  full_name text,
  business_name text,
  business_description text,
  business_industry text,
  business_timezone text DEFAULT 'UTC'::text,
  preferred_language text DEFAULT 'en'::text,
  default_reply_tone text DEFAULT 'professional'::text,
  sender_summary_threshold integer DEFAULT 20,
  notifications_email text,
  notifications_enabled boolean DEFAULT true,
  telegram_bot_token text,
  telegram_webhook_secret text,
  memory_context text,
  soul_context text,
  rule_context text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

CREATE TABLE public.external_identities (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  external_id text NOT NULL,
  external_type text,
  entity_role text NOT NULL,
  entity_id uuid NOT NULL,
  is_primary boolean DEFAULT true,
  identity_metadata jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT external_identities_pkey PRIMARY KEY (id),
  CONSTRAINT external_identities_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);
CREATE UNIQUE INDEX ix_external_identities_external_id ON public.external_identities USING btree (owner_id, external_type, external_id);

CREATE TABLE public.customers (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  name text NOT NULL,
  email text,
  phone text,
  company text,
  status text DEFAULT 'active'::text,
  preference text,
  notes text,
  telegram_user_id text,
  telegram_username text,
  telegram_chat_id text,
  last_contact date,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT customers_pkey PRIMARY KEY (id),
  CONSTRAINT customers_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);
CREATE UNIQUE INDEX ix_customers_owner_telegram_user_id ON public.customers USING btree (owner_id, telegram_user_id) WHERE (telegram_user_id IS NOT NULL);

CREATE TABLE public.products (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  name text NOT NULL,
  description text,
  selling_price numeric,
  cost_price numeric DEFAULT 0,
  stock_number integer DEFAULT 0,
  product_link text,
  category text,
  description_embedding vector(1536),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT products_pkey PRIMARY KEY (id),
  CONSTRAINT products_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.suppliers (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  name text NOT NULL,
  email text,
  phone text,
  category text,
  contract_notes text,
  status text DEFAULT 'active'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT suppliers_pkey PRIMARY KEY (id),
  CONSTRAINT suppliers_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.investors (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  name text NOT NULL,
  email text,
  phone text,
  focus text,
  notes text,
  status text DEFAULT 'active'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT investors_pkey PRIMARY KEY (id),
  CONSTRAINT investors_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.partners (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  name text NOT NULL,
  email text,
  phone text,
  partner_type text,
  notes text,
  status text DEFAULT 'active'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT partners_pkey PRIMARY KEY (id),
  CONSTRAINT partners_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.policy_chunks (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  source_file text NOT NULL,
  page_number integer DEFAULT 0,
  chunk_index integer DEFAULT 0,
  chunk_text text NOT NULL,
  subheading text,
  category text,
  hard_constraint boolean DEFAULT false,
  embedding vector(1536) NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT policy_chunks_pkey PRIMARY KEY (id),
  CONSTRAINT policy_chunks_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.conversation_threads (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  thread_type text NOT NULL,
  title text,
  sender_external_id text,
  sender_name text,
  sender_role text,
  sender_channel text,
  last_message_at timestamp with time zone DEFAULT now(),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT conversation_threads_pkey PRIMARY KEY (id),
  CONSTRAINT conversation_threads_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT conversation_threads_thread_type_check CHECK (thread_type = ANY (ARRAY['owner_chat'::text, 'external_sender'::text])),
  CONSTRAINT conversation_threads_external_sender_requirements_check CHECK (
    thread_type <> 'external_sender'::text
    OR sender_external_id IS NOT NULL
  )
);
CREATE INDEX ix_conversation_threads_owner_type ON public.conversation_threads USING btree (owner_id, thread_type);
CREATE INDEX ix_conversation_threads_owner_last_message_at ON public.conversation_threads USING btree (owner_id, last_message_at DESC);
CREATE UNIQUE INDEX ux_conversation_threads_external_sender ON public.conversation_threads USING btree (owner_id, thread_type, sender_channel, sender_external_id) WHERE (thread_type = 'external_sender'::text);

CREATE TABLE public.messages (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  conversation_thread_id uuid,
  sender_id text,
  sender_name text,
  sender_role text,
  direction text,
  content text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT messages_pkey PRIMARY KEY (id),
  CONSTRAINT messages_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT messages_conversation_thread_id_fkey FOREIGN KEY (conversation_thread_id) REFERENCES public.conversation_threads(id)
);
CREATE INDEX ix_messages_owner_thread_created_at ON public.messages USING btree (owner_id, conversation_thread_id, created_at DESC);

CREATE TABLE public.memory_entries (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  sender_id text,
  sender_name text,
  sender_role text,
  memory_type text NOT NULL,
  content text NOT NULL,
  summary text,
  tags text[] DEFAULT '{}'::text[],
  importance numeric DEFAULT 0.5,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT memory_entries_pkey PRIMARY KEY (id),
  CONSTRAINT memory_entries_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.memory_update_proposals (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  target_table text NOT NULL,
  target_id uuid,
  proposed_content jsonb NOT NULL,
  reason text,
  risk_level text DEFAULT 'low'::text,
  status text DEFAULT 'pending'::text,
  created_at timestamp with time zone DEFAULT now(),
  reviewed_at timestamp with time zone,
  CONSTRAINT memory_update_proposals_pkey PRIMARY KEY (id),
  CONSTRAINT memory_update_proposals_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.held_replies (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  thread_id text,
  sender_id text,
  sender_name text,
  sender_role text,
  reply_text text NOT NULL,
  risk_level text DEFAULT 'medium'::text,
  risk_flags jsonb DEFAULT '[]'::jsonb,
  status text DEFAULT 'pending'::text,
  reviewer_notes text,
  created_at timestamp with time zone DEFAULT now(),
  reviewed_at timestamp with time zone,
  CONSTRAINT held_replies_pkey PRIMARY KEY (id),
  CONSTRAINT held_replies_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE OR REPLACE FUNCTION public.purchase_product_atomic(
  p_owner_id uuid,
  p_customer_id uuid,
  p_product_id uuid,
  p_quantity integer,
  p_order_id uuid,
  p_order_date date,
  p_channel text DEFAULT 'website'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_selling_price numeric;
  v_remaining_stock integer;
  v_total_price numeric;
BEGIN
  IF p_quantity IS NULL OR p_quantity < 1 THEN
    RAISE EXCEPTION 'INVALID_QUANTITY';
  END IF;

  PERFORM 1
  FROM public.customers
  WHERE id = p_customer_id AND owner_id = p_owner_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'CUSTOMER_NOT_FOUND';
  END IF;

  UPDATE public.products
  SET stock_number = stock_number - p_quantity,
      updated_at = now()
  WHERE id = p_product_id
    AND owner_id = p_owner_id
    AND COALESCE(stock_number, 0) >= p_quantity
  RETURNING selling_price, stock_number
  INTO v_selling_price, v_remaining_stock;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'OUT_OF_STOCK_OR_PRODUCT_NOT_FOUND';
  END IF;

  v_total_price = COALESCE(v_selling_price, 0) * p_quantity;

  INSERT INTO public.orders (
    id,
    owner_id,
    customer_id,
    product_id,
    quantity,
    total_price,
    order_date,
    status,
    channel
  )
  VALUES (
    p_order_id,
    p_owner_id,
    p_customer_id,
    p_product_id,
    p_quantity,
    v_total_price,
    p_order_date,
    'paid',
    p_channel
  );

  RETURN jsonb_build_object(
    'order_id', p_order_id,
    'total_price', v_total_price,
    'remaining_stock', v_remaining_stock
  );
END;
$$;

CREATE TABLE public.owner_memory_rules (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  role text NOT NULL,
  category text NOT NULL,
  content text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT owner_memory_rules_pkey PRIMARY KEY (id),
  CONSTRAINT owner_memory_rules_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.entity_memories (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  entity_role text NOT NULL,
  entity_id uuid NOT NULL,
  memory_type text NOT NULL,
  content text NOT NULL,
  summary text,
  tags text[] DEFAULT '{}'::text[],
  importance integer DEFAULT 1,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT entity_memories_pkey PRIMARY KEY (id),
  CONSTRAINT entity_memories_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

CREATE TABLE public.conversation_memories (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  conversation_thread_id uuid,
  entity_role text,
  entity_id uuid,
  summary text NOT NULL,
  keywords text[] DEFAULT '{}'::text[],
  happened_at timestamp with time zone DEFAULT now(),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT conversation_memories_pkey PRIMARY KEY (id),
  CONSTRAINT conversation_memories_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT conversation_memories_conversation_thread_id_fkey FOREIGN KEY (conversation_thread_id) REFERENCES public.conversation_threads(id)
);

CREATE TABLE public.daily_digest (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  title text NOT NULL,
  summary text,
  risk text DEFAULT 'low'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT daily_digest_pkey PRIMARY KEY (id),
  CONSTRAINT daily_digest_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);

-- ==========================================
-- LEVEL 1: Tables referencing Level 0
-- ==========================================

CREATE TABLE public.conversation_sender_memories (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  conversation_thread_id uuid NOT NULL,
  sender_external_id text NOT NULL,
  sender_name text,
  sender_role text,
  summary text NOT NULL,
  message_count_since_update integer DEFAULT 0,
  last_message_at timestamp with time zone,
  last_summarized_at timestamp with time zone DEFAULT now(),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT conversation_sender_memories_pkey PRIMARY KEY (id),
  CONSTRAINT conversation_sender_memories_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT conversation_sender_memories_conversation_thread_id_fkey FOREIGN KEY (conversation_thread_id) REFERENCES public.conversation_threads(id)
);
CREATE UNIQUE INDEX ux_conversation_sender_memories_owner_thread_sender ON public.conversation_sender_memories USING btree (owner_id, conversation_thread_id, sender_external_id);
CREATE INDEX ix_conversation_sender_memories_owner_updated_at ON public.conversation_sender_memories USING btree (owner_id, updated_at DESC);

CREATE TABLE public.orders (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  customer_id uuid NOT NULL,
  product_id uuid NOT NULL,
  quantity integer DEFAULT 1,
  total_price numeric(10, 2) DEFAULT 0,
  order_date date DEFAULT CURRENT_DATE,
  status text DEFAULT 'pending'::text,
  channel text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT orders_pkey PRIMARY KEY (id),
  CONSTRAINT orders_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT orders_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id),
  CONSTRAINT orders_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id)
);

CREATE TABLE public.supplier_products (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  supplier_id uuid NOT NULL,
  product_id uuid NOT NULL,
  supply_price numeric,
  stock_we_buy integer DEFAULT 0,
  contract text,
  lead_time_days integer,
  contract_start date,
  contract_end date,
  is_active boolean DEFAULT true,
  notes text,
  notes_embedding vector(1536),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT supplier_products_pkey PRIMARY KEY (id),
  CONSTRAINT supplier_products_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT supplier_products_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id),
  CONSTRAINT supplier_products_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id)
);



CREATE TABLE public.partner_agreements (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  partner_id uuid NOT NULL,
  description text NOT NULL,
  agreement_type text DEFAULT 'general'::text,
  revenue_share_pct numeric(5, 2),
  start_date date,
  end_date date,
  is_active boolean DEFAULT true,
  notes text,
  description_embedding vector(1536),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT partner_agreements_pkey PRIMARY KEY (id),
  CONSTRAINT partner_agreements_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT partner_agreements_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.partners(id)
);

CREATE TABLE public.pending_approvals (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  title text NOT NULL,
  sender text,
  preview text,
  proposal_type text,
  risk_level text DEFAULT 'low'::text,
  status text DEFAULT 'pending'::text,
  proposal_id uuid,
  held_reply_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT pending_approvals_pkey PRIMARY KEY (id),
  CONSTRAINT pending_approvals_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT pending_approvals_proposal_id_fkey FOREIGN KEY (proposal_id) REFERENCES public.memory_update_proposals(id),
  CONSTRAINT pending_approvals_held_reply_id_fkey FOREIGN KEY (held_reply_id) REFERENCES public.held_replies(id)
);

CREATE TABLE public.reply_review_records (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  trace_id text,
  thread_id text,
  sender_id text,
  sender_name text,
  sender_role text,
  raw_message text,
  reply_text text,
  risk_level text,
  risk_flags jsonb DEFAULT '[]'::jsonb,
  approval_rule_flags jsonb DEFAULT '[]'::jsonb,
  requires_approval boolean,
  final_decision text,
  review_label text,
  reviewer_reason text,
  held_reply_id uuid,
  message_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  reviewed_at timestamp with time zone,
  CONSTRAINT reply_review_records_pkey PRIMARY KEY (id),
  CONSTRAINT reply_review_records_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT reply_review_records_held_reply_id_fkey FOREIGN KEY (held_reply_id) REFERENCES public.held_replies(id),
  CONSTRAINT reply_review_records_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id)
);

-- ==========================================
-- LEVEL 2: Tables referencing Level 1
-- ==========================================

CREATE TABLE public.partner_product_relations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  partner_id uuid NOT NULL,
  product_id uuid NOT NULL,
  agreement_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT partner_product_relations_pkey PRIMARY KEY (id),
  CONSTRAINT partner_product_relations_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT partner_product_relations_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.partners(id),
  CONSTRAINT partner_product_relations_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id),
  CONSTRAINT partner_product_relations_agreement_id_fkey FOREIGN KEY (agreement_id) REFERENCES public.partner_agreements(id)
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'investor_product_metrics'
  ) THEN
    EXECUTE 'ALTER TABLE public.investor_product_metrics ENABLE ROW LEVEL SECURITY';
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'public'
        AND tablename = 'investor_product_metrics'
        AND policyname = 'owner_access_investor_product_metrics'
    ) THEN
      EXECUTE 'CREATE POLICY owner_access_investor_product_metrics ON public.investor_product_metrics USING (owner_id = auth.uid())';
    END IF;
  END IF;
END
$$;
