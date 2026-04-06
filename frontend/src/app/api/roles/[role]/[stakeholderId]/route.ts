import { getAuthenticatedClient } from "@/lib/api";
import { roleTableMap, stakeholderRoles, type StakeholderRole } from "@/lib/stakeholder-config";
import type { StakeholderInput } from "@/lib/types";
import { NextResponse } from "next/server";

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
  const { data, error } = await auth.supabase
    .from(table)
    .update({ ...payload, name: payload.name?.trim() })
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
  const { error } = await auth.supabase
    .from(table)
    .update({ status: "inactive" })
    .eq("owner_id", auth.user.id)
    .eq("id", stakeholderId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  await auth.supabase
    .from("external_identities")
    .delete()
    .eq("owner_id", auth.user.id)
    .eq("entity_role", role.slice(0, -1))
    .eq("entity_id", stakeholderId);

  return NextResponse.json({ ok: true });
}
