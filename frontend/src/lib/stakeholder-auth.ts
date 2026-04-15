import "server-only";

import type { User, SupabaseClient } from "@supabase/supabase-js";

const stakeholderTableByRole = {
  customer: "customers",
  supplier: "suppliers",
  partner: "partners",
  investor: "investors",
} as const;

type StakeholderRole = keyof typeof stakeholderTableByRole;
export type { StakeholderRole };

type StakeholderRow = {
  id: string;
  owner_id: string;
  name: string | null;
  email?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  telegram_user_id?: string | null;
  telegram_chat_id?: string | null;
};

export async function resolveAuthenticatedStakeholder(
  admin: SupabaseClient,
  user: User,
): Promise<{ role: StakeholderRole; table: string; stakeholder: StakeholderRow } | null> {
  const { data: identity } = await admin
    .from("external_identities")
    .select("owner_id, entity_id, entity_role")
    .contains("identity_metadata", { supabase_user_id: user.id })
    .limit(1)
    .maybeSingle();

  const entityRole = identity?.entity_role;
  if (!identity?.entity_id || !entityRole || !(entityRole in stakeholderTableByRole)) {
    return null;
  }

  const stakeholderRole = entityRole as StakeholderRole;
  const table = stakeholderTableByRole[stakeholderRole];

  const { data: stakeholder } = await admin
    .from(table)
    .select("*")
    .eq("owner_id", identity.owner_id)
    .eq("id", identity.entity_id)
    .maybeSingle();

  if (stakeholder) {
    return { role: stakeholderRole, table, stakeholder: stakeholder as StakeholderRow };
  }

  return null;
}

export function stakeholderSenderExternalId(stakeholder: StakeholderRow, user: User): string {
  return (
    stakeholder.email ||
    stakeholder.phone ||
    stakeholder.telegram_user_id ||
    stakeholder.telegram_username ||
    user.email ||
    user.id
  );
}
