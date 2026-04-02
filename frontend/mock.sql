insert into public.memory_entries (
  owner_id,
  sender_id,
  sender_name,
  sender_role,
  memory_type,
  content,
  summary,
  tags,
  importance
)
values
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'cust-1',
  'Acme Corp',
  'customer',
  'preference',
  'Customer prefers concise replies and wants invoices sent on the 1st of each month.',
  'Prefers concise replies; invoices on 1st.',
  ARRAY['customer', 'preference', 'invoice'],
  0.85
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'supp-1',
  'TechParts Ltd',
  'supplier',
  'constraint',
  'Supplier requested Net-30 payment terms for future orders.',
  'Requested Net-30 payment terms.',
  ARRAY['supplier', 'payment-terms'],
  0.9
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'inv-1',
  'Vertex Ventures',
  'investor',
  'preference',
  'Investor wants quarterly updates focused on CAC, churn, and runway.',
  'Wants quarterly updates on CAC, churn, runway.',
  ARRAY['investor', 'metrics', 'preference'],
  0.8
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'cust-2',
  'Beta Retail',
  'customer',
  'relationship_signal',
  'Customer showed frustration about delivery delays and wants proactive updates.',
  'Frustrated about delays; wants proactive updates.',
  ARRAY['customer', 'relationship', 'delivery'],
  0.75
);

insert into public.messages (
  owner_id,
  sender_id,
  sender_name,
  sender_role,
  direction,
  content
)
values
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'cust-1',
  'Acme Corp',
  'customer',
  'inbound',
  'We prefer shorter replies and need invoices on the 1st every month.'
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'cust-1',
  'Acme Corp',
  'customer',
  'outbound',
  'Understood. We will keep replies concise and send invoices on the 1st.'
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'supp-1',
  'TechParts Ltd',
  'supplier',
  'inbound',
  'For the next shipment, we require Net-30 payment terms.'
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'inv-1',
  'Vertex Ventures',
  'investor',
  'inbound',
  'Please include CAC and churn prominently in the next quarterly update.'
);

insert into public.pending_approvals (
  owner_id,
  title,
  sender,
  preview,
  proposal_type,
  risk_level,
  status
)
values
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'Memory update requires approval',
  'Memory Agent',
  'Add memory: Customer prefers concise replies and monthly invoices on the 1st.',
  'memory-update',
  'medium',
  'pending'
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'Memory update requires approval',
  'Memory Agent',
  'Add memory: Supplier requested Net-30 payment terms.',
  'memory-update',
  'high',
  'pending'
);

insert into public.held_replies (
  id,
  owner_id,
  thread_id,
  sender_id,
  sender_name,
  sender_role,
  reply_text,
  risk_level,
  risk_flags,
  status
)
values (
  '11111111-1111-1111-1111-111111111111',
  'PASTE_YOUR_OWNER_ID_HERE',
  'cust-2-thread',
  'cust-2',
  'Beta Retail',
  'customer',
  'We can offer a replacement after owner review because your delivery delay exceeds our normal policy window.',
  'medium',
  '[]'::jsonb,
  'pending'
);

insert into public.pending_approvals (
  owner_id,
  title,
  sender,
  preview,
  proposal_type,
  risk_level,
  status,
  held_reply_id
)
values (
  'PASTE_YOUR_OWNER_ID_HERE',
  'Reply requires approval (medium risk)',
  'Beta Retail',
  'We can offer a replacement after owner review because your delivery delay exceeds our normal policy window.',
  'reply-approval',
  'medium',
  'pending',
  '11111111-1111-1111-1111-111111111111'
);

insert into public.memory_update_proposals (
  owner_id,
  sender_id,
  sender_name,
  sender_role,
  target_table,
  proposed_content,
  risk_level,
  reason,
  status
)
values
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'cust-1',
  'Acme Corp',
  'customer',
  'memory_entries',
  '[
    {
      "sender_id": "cust-1",
      "sender_name": "Acme Corp",
      "sender_role": "customer",
      "memory_type": "preference",
      "content": "Customer prefers concise replies and monthly invoices on the 1st.",
      "summary": "Prefers concise replies; invoices on 1st.",
      "tags": ["customer", "preference", "invoice"],
      "importance": 0.85
    }
  ]'::jsonb,
  'medium',
  'Mock proposal for frontend testing',
  'pending'
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'supp-1',
  'TechParts Ltd',
  'supplier',
  'memory_entries',
  '[
    {
      "sender_id": "supp-1",
      "sender_name": "TechParts Ltd",
      "sender_role": "supplier",
      "memory_type": "constraint",
      "content": "Supplier requested Net-30 payment terms for future orders.",
      "summary": "Requested Net-30 payment terms.",
      "tags": ["supplier", "payment-terms"],
      "importance": 0.9
    }
  ]'::jsonb,
  'high',
  'Mock supplier constraint proposal',
  'pending'
)
returning id;

insert into public.pending_approvals (
  owner_id,
  title,
  sender,
  preview,
  proposal_type,
  risk_level,
  status,
  proposal_id
)
values
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'Memory update requires approval',
  'Memory Agent',
  'Add memory: Customer prefers concise replies and invoices on the 1st.',
  'memory-update',
  'medium',
  'pending',
  'PASTE_FIRST_PROPOSAL_ID_HERE'
),
(
  'PASTE_YOUR_OWNER_ID_HERE',
  'Memory update requires approval',
  'Memory Agent',
  'Add memory: Supplier requested Net-30 payment terms.',
  'memory-update',
  'high',
  'pending',
  'PASTE_SECOND_PROPOSAL_ID_HERE'
);
