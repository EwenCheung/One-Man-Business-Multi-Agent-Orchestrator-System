import { getAuthenticatedClient } from "@/lib/api";
import { appendSwitchNote, roleTableMap, stakeholderRoles, type StakeholderRole } from "@/lib/stakeholder-config";
import type { StakeholderSwitchInput } from "@/lib/types";
import { NextResponse } from "next/server";

function noteField(role: StakeholderRole) {
  if (role === "suppliers") return "contract_notes";
  return role === "customers" || role === "investors" || role === "partners" ? "notes" : null;
}

function pickTargetPayload(source: Record<string, unknown>, targetRole: StakeholderRole) {
  const base = {
    name: source.name,
    email: source.email,
    phone: source.phone,
    status: "active",
  };

  if (targetRole === "customers") {
    return { ...base, company: source.company ?? null, preference: null, notes: source.notes ?? source.contract_notes ?? null };
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

  const { data: targetRow, error: insertError } = await auth.supabase
    .from(targetTable)
    .insert({ id: crypto.randomUUID(), owner_id: auth.user.id, ...pickTargetPayload(sourceRow, payload.targetRole) })
    .select("*")
    .single();

  if (insertError || !targetRow) {
    return NextResponse.json({ error: insertError?.message ?? "Failed to create target role." }, { status: 400 });
  }

  const sourceNoteField = noteField(payload.sourceRole);
  const sourcePatch: Record<string, unknown> = { status: "inactive" };
  if (sourceNoteField) {
    sourcePatch[sourceNoteField] = appendSwitchNote(
      (sourceRow[sourceNoteField] as string | null | undefined) ?? null,
      payload.targetRole.slice(0, -1)
    );
  }

  const sourceUpdate = await auth.supabase
    .from(sourceTable)
    .update(sourcePatch)
    .eq("owner_id", auth.user.id)
    .eq("id", payload.sourceId);

  if (sourceUpdate.error) {
    return NextResponse.json({ error: sourceUpdate.error.message }, { status: 400 });
  }

  const identityUpdate = await auth.supabase
    .from("external_identities")
    .update({ entity_role: payload.targetRole.slice(0, -1), entity_id: targetRow.id })
    .eq("owner_id", auth.user.id)
    .eq("entity_role", payload.sourceRole.slice(0, -1))
    .eq("entity_id", payload.sourceId);

  if (identityUpdate.error) {
    return NextResponse.json({ error: identityUpdate.error.message }, { status: 400 });
  }

  return NextResponse.json({ ...targetRow, role: payload.targetRole });
}
