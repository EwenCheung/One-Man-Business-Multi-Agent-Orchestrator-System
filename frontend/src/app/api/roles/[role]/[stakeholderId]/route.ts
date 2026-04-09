import { getAuthenticatedClient } from "@/lib/api";
import { roleTableMap, stakeholderRoles, type StakeholderRole } from "@/lib/stakeholder-config";
import type { StakeholderInput } from "@/lib/types";
import type { SupabaseClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

const allowedFieldsByRole: Record<StakeholderRole, string[]> = {
  customers: ["name", "telegram_username", "email", "phone", "company", "status", "preference", "notes"],
  suppliers: ["name", "email", "phone", "category", "status", "contract_notes"],
  investors: ["name", "email", "phone", "focus", "status", "notes"],
  partners: ["name", "email", "phone", "partner_type", "status", "notes"],
};

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
    if ((count ?? 0) > 0) return `Cannot delete customer because ${count} order(s) still reference this customer.`;
    return null;
  }

  if (role === "suppliers") {
    const { count, error } = await supabase
      .from("supplier_products")
      .select("id", { count: "exact", head: true })
      .eq("owner_id", ownerId)
      .eq("supplier_id", stakeholderId);
    if (error) return error.message;
    if ((count ?? 0) > 0) return `Cannot delete supplier because ${count} supply contract row(s) still reference this supplier.`;
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
      return `Cannot delete partner because ${agreementResult.count} agreement(s) still reference this partner.`;
    }

    const productRelationResult = await supabase
      .from("partner_product_relations")
      .select("id", { count: "exact", head: true })
      .eq("owner_id", ownerId)
      .eq("partner_id", stakeholderId);
    if (productRelationResult.error) return productRelationResult.error.message;
    if ((productRelationResult.count ?? 0) > 0) {
      return `Cannot delete partner because ${productRelationResult.count} partner product relation(s) still reference this partner.`;
    }
  }

  return null;
}

function sanitizeStakeholderPayload(role: StakeholderRole, payload: StakeholderInput) {
  const allowedFields = allowedFieldsByRole[role];
  return Object.fromEntries(
    Object.entries(payload).filter(([key]) => allowedFields.includes(key))
  );
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ role: string; stakeholderId: string }> }
) {
  const { role, stakeholderId } = await params;

  if (!stakeholderRoles.includes(role as StakeholderRole)) {
    return NextResponse.json({ error: "Unsupported role." }, { status: 404 });
  }

  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as StakeholderInput;
  const table = roleTableMap[role as StakeholderRole];
  const sanitizedPayload = sanitizeStakeholderPayload(role as StakeholderRole, payload);
  const { data, error } = await auth.supabase
    .from(table)
    .update({ ...sanitizedPayload, name: payload.name?.trim() })
    .eq("owner_id", auth.user.id)
    .eq("id", stakeholderId)
    .select("*")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json({ ...data, role });
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ role: string; stakeholderId: string }> }
) {
  void request;
  const { role, stakeholderId } = await params;

  if (!stakeholderRoles.includes(role as StakeholderRole)) {
    return NextResponse.json({ error: "Unsupported role." }, { status: 404 });
  }

  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const table = roleTableMap[role as StakeholderRole];
  const dependencyError = await getStakeholderDependencyError(
    auth.supabase,
    auth.user.id,
    role as StakeholderRole,
    stakeholderId
  );

  if (dependencyError) {
    return NextResponse.json({ error: dependencyError }, { status: 409 });
  }

  const identityDelete = await auth.supabase
    .from("external_identities")
    .delete()
    .eq("owner_id", auth.user.id)
    .eq("entity_role", role.slice(0, -1))
    .eq("entity_id", stakeholderId);

  if (identityDelete.error) {
    return NextResponse.json({ error: identityDelete.error.message }, { status: 400 });
  }

  const { error } = await auth.supabase
    .from(table)
    .delete()
    .eq("owner_id", auth.user.id)
    .eq("id", stakeholderId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json({ ok: true });
}
