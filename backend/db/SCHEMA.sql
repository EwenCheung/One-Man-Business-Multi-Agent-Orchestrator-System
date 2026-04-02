-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.conversation_memories (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  entity_role text,
  entity_id uuid,
  summary text NOT NULL,
  keywords ARRAY DEFAULT '{}'::text[],
  happened_at timestamp with time zone DEFAULT now(),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT conversation_memories_pkey PRIMARY KEY (id),
  CONSTRAINT conversation_memories_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);
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
  last_contact date,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT customers_pkey PRIMARY KEY (id),
  CONSTRAINT customers_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
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
CREATE TABLE public.entity_memories (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  entity_role text NOT NULL,
  entity_id uuid NOT NULL,
  memory_type text NOT NULL,
  content text NOT NULL,
  summary text,
  tags ARRAY DEFAULT '{}'::text[],
  importance integer DEFAULT 1,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT entity_memories_pkey PRIMARY KEY (id),
  CONSTRAINT entity_memories_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);
CREATE TABLE public.investor_product_metrics (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  product_id uuid NOT NULL,
  cost numeric,
  selling_price numeric,
  roi numeric,
  daily_sales integer DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT investor_product_metrics_pkey PRIMARY KEY (id),
  CONSTRAINT investor_product_metrics_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id),
  CONSTRAINT investor_product_metrics_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
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
CREATE TABLE public.memory_entries (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  sender_id text,
  sender_name text,
  sender_role text,
  memory_type text NOT NULL,
  content text NOT NULL,
  summary text,
  tags ARRAY DEFAULT '{}'::text[],
  importance numeric DEFAULT 0.5,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
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
CREATE TABLE public.messages (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  sender_id text,
  sender_name text,
  sender_role text,
  direction text,
  content text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT messages_pkey PRIMARY KEY (id),
  CONSTRAINT messages_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);
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
CREATE TABLE public.partner_agreements (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  partner_id uuid NOT NULL,
  description text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT partner_agreements_pkey PRIMARY KEY (id),
  CONSTRAINT partner_agreements_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT partner_agreements_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.partners(id)
);
CREATE TABLE public.partner_product_relations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  partner_id uuid NOT NULL,
  product_id uuid NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT partner_product_relations_pkey PRIMARY KEY (id),
  CONSTRAINT partner_product_relations_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT partner_product_relations_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.partners(id),
  CONSTRAINT partner_product_relations_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id)
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
CREATE TABLE public.pending_approvals (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  title text NOT NULL,
  sender text,
  preview text,
  proposal_type text,
  risk_level text DEFAULT 'low'::text,
  status text DEFAULT 'pending'::text,
  created_at timestamp with time zone DEFAULT now(),
  proposal_id uuid,
  held_reply_id uuid,
  CONSTRAINT pending_approvals_pkey PRIMARY KEY (id),
  CONSTRAINT pending_approvals_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT pending_approvals_proposal_id_fkey FOREIGN KEY (proposal_id) REFERENCES public.memory_update_proposals(id),
  CONSTRAINT pending_approvals_held_reply_id_fkey FOREIGN KEY (held_reply_id) REFERENCES public.held_replies(id)
);
CREATE TABLE public.products (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  name text NOT NULL,
  description text,
  selling_price numeric,
  stock_number integer DEFAULT 0,
  product_link text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT products_pkey PRIMARY KEY (id),
  CONSTRAINT products_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);
CREATE TABLE public.profiles (
  id uuid NOT NULL,
  full_name text,
  business_name text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);
CREATE TABLE public.supplier_products (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  supplier_id uuid NOT NULL,
  product_id uuid NOT NULL,
  supply_price numeric,
  stock_we_buy integer DEFAULT 0,
  contract text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT supplier_products_pkey PRIMARY KEY (id),
  CONSTRAINT supplier_products_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id),
  CONSTRAINT supplier_products_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id),
  CONSTRAINT supplier_products_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id)
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
