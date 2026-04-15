import { getAuthenticatedClient } from "@/lib/api";
import { createAdminClient } from "@/lib/supabase/admin";
import { roleTableMap, stakeholderRoles, type StakeholderRole } from "@/lib/stakeholder-config";
import type { StakeholderSwitchInput } from "@/lib/types";
import type { SupabaseClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

async function syncAuthRolesForStakeholder(
  supabase: SupabaseClient,
  ownerId: string,
  sourceRole: StakeholderRole,
  sourceId: string,
  targetRole: StakeholderRole,
) {
  const { data: identities, error } = await supabase
    .from("external_identities")
    .select("identity_metadata")
    .eq("owner_id", ownerId)
    .eq("entity_role", sourceRole.slice(0, -1))
    .eq("entity_id", sourceId);

  if (error || !identities?.length) {
    return error?.message ?? null;
  }

  const nextRole = targetRole.slice(0, -1);
  for (const identity of identities) {
    const userId = identity.identity_metadata?.supabase_user_id;
    if (!userId) continue;

    const current = await supabase.auth.admin.getUserById(userId);
    if (current.error || !current.data.user) {
      return current.error?.message ?? "Failed to load auth user.";
    }

    const update = await supabase.auth.admin.updateUserById(userId, {
      user_metadata: {
        ...(current.data.user.user_metadata ?? {}),
        role: nextRole,
        owner_id: ownerId,
      },
    });
    if (update.error) {
      return update.error.message;
    }
  }

  return null;
}

async function getStakeholderDependencyError(
  supabase: SupabaseClient,
  ownerId: string,
  role: StakeholderRole,
  stakeholderId: string
) {
  if (role === "customers") {
    const { count, error } = await supabase
      .from("orders")
      .select("id", { count: "exact", head: true })
      .eq("owner_id", ownerId)
      .eq("customer_id", stakeholderId);
    if (error) return error.message;
    if ((count ?? 0) > 0) return `Cannot switch customer role because ${count} order(s) still reference this customer.`;
    return null;
  }

  if (role === "suppliers") {
    const { count, error } = await supabase
      .from("supplier_products")
      .select("id", { count: "exact", head: true })
      .eq("owner_id", ownerId)
      .eq("supplier_id", stakeholderId);
    if (error) return error.message;
    if ((count ?? 0) > 0) return `Cannot switch supplier role because ${count} supply contract row(s) still reference this supplier.`;
    return null;
  }

  if (role === "partners") {
    const agreementResult = await supabase
      .from("partner_agreements")
      .select("id", { count: "exact", head: true })
      .eq("owner_id", ownerId)
      .eq("partner_id", stakeholderId);
    if (agreementResult.error) return agreementResult.error.message;
    if ((agreementResult.count ?? 0) > 0) {
      return `Cannot switch partner role because ${agreementResult.count} agreement(s) still reference this partner.`;
    }

    const productRelationResult = await supabase
      .from("partner_product_relations")
      .select("id", { count: "exact", head: true })
      .eq("owner_id", ownerId)
      .eq("partner_id", stakeholderId);
    if (productRelationResult.error) return productRelationResult.error.message;
    if ((productRelationResult.count ?? 0) > 0) {
      return `Cannot switch partner role because ${productRelationResult.count} partner product relation(s) still reference this partner.`;
    }
  }

  return null;
}

function pickTargetPayload(source: Record<string, unknown>, targetRole: StakeholderRole) {
  const base = {
    name: source.name,
    email: source.email,
    phone: source.phone,
    status: "active",
  };

  if (targetRole === "customers") {
    return {
      ...base,
      telegram_username: source.telegram_username ?? null,
      company: source.company ?? null,
      preference: null,
      notes: source.notes ?? source.contract_notes ?? null,
    };
  }
  if (targetRole === "suppliers") {
    return { ...base, category: source.category ?? null, contract_notes: source.notes ?? source.contract_notes ?? null };
  }
  if (targetRole === "investors") {
    return { ...base, focus: source.focus ?? null, notes: source.notes ?? source.contract_notes ?? null };
  }
  return { ...base, partner_type: source.partner_type ?? null, notes: source.notes ?? source.contract_notes ?? null };
}

export async function POST(request: Request) {
  const auth = await getAuthenticatedClient({ redirectOnFail: false });
  const admin = createAdminClient();

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as StakeholderSwitchInput;

  if (
    !stakeholderRoles.includes(payload.sourceRole) ||
    !stakeholderRoles.includes(payload.targetRole) ||
    payload.sourceRole === payload.targetRole
  ) {
    return NextResponse.json({ error: "Invalid role switch request." }, { status: 400 });
  }

  const sourceTable = roleTableMap[payload.sourceRole];
  const targetTable = roleTableMap[payload.targetRole];

  const { data: sourceRow, error: sourceError } = await auth.supabase
    .from(sourceTable)
    .select("*")
    .eq("owner_id", auth.user.id)
    .eq("id", payload.sourceId)
    .single();

  if (sourceError || !sourceRow) {
    return NextResponse.json({ error: sourceError?.message ?? "Source stakeholder not found." }, { status: 404 });
  }

  const dependencyError = await getStakeholderDependencyError(
    auth.supabase,
    auth.user.id,
    payload.sourceRole,
    payload.sourceId
  );

  if (dependencyError) {
    return NextResponse.json({ error: dependencyError }, { status: 409 });
  }

  const { data: targetRow, error: insertError } = await auth.supabase
    .from(targetTable)
    .insert({ id: crypto.randomUUID(), owner_id: auth.user.id, ...pickTargetPayload(sourceRow, payload.targetRole) })
    .select("*")
    .single();

  if (insertError || !targetRow) {
    return NextResponse.json({ error: insertError?.message ?? "Failed to create target role." }, { status: 400 });
  }

  const identityUpdate = await auth.supabase
    .from("external_identities")
    .update({ entity_role: payload.targetRole.slice(0, -1), entity_id: targetRow.id })
    .eq("owner_id", auth.user.id)
    .eq("entity_role", payload.sourceRole.slice(0, -1))
    .eq("entity_id", payload.sourceId);

  if (identityUpdate.error) {
    await auth.supabase.from(targetTable).delete().eq("owner_id", auth.user.id).eq("id", targetRow.id);
    return NextResponse.json({ error: identityUpdate.error.message }, { status: 400 });
  }

  const sourceDelete = await auth.supabase
    .from(sourceTable)
    .delete()
    .eq("owner_id", auth.user.id)
    .eq("id", payload.sourceId);

  if (sourceDelete.error) {
    await auth.supabase
      .from("external_identities")
      .update({ entity_role: payload.sourceRole.slice(0, -1), entity_id: payload.sourceId })
      .eq("owner_id", auth.user.id)
      .eq("entity_role", payload.targetRole.slice(0, -1))
      .eq("entity_id", targetRow.id);
    await auth.supabase.from(targetTable).delete().eq("owner_id", auth.user.id).eq("id", targetRow.id);
    return NextResponse.json({ error: sourceDelete.error.message }, { status: 400 });
  }

  const authSyncError = await syncAuthRolesForStakeholder(
    admin,
    auth.user.id,
    payload.sourceRole,
    payload.sourceId,
    payload.targetRole
  );

  if (authSyncError) {
    return NextResponse.json(
      { ...targetRow, role: payload.targetRole, warning: `Role switched, but auth role sync failed: ${authSyncError}` },
      { status: 200 }
    );
  }

  return NextResponse.json({ ...targetRow, role: payload.targetRole });
}
