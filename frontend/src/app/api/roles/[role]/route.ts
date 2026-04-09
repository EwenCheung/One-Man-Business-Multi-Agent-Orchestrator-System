import { getAuthenticatedClient } from "@/lib/api";
import { roleTableMap, stakeholderRoles, type StakeholderRole } from "@/lib/stakeholder-config";
import type { StakeholderInput } from "@/lib/types";
import { NextResponse } from "next/server";

const allowedFieldsByRole: Record<StakeholderRole, string[]> = {
  customers: ["name", "telegram_username", "email", "phone", "company", "status", "preference", "notes"],
  suppliers: ["name", "email", "phone", "category", "status", "contract_notes"],
  investors: ["name", "email", "phone", "focus", "status", "notes"],
  partners: ["name", "email", "phone", "partner_type", "status", "notes"],
};

function sanitizeStakeholderPayload(role: StakeholderRole, payload: StakeholderInput) {
  const allowedFields = allowedFieldsByRole[role];
  return Object.fromEntries(
    Object.entries(payload).filter(([key]) => allowedFields.includes(key))
  );
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ role: string }> }
) {
  void request;
  const { role } = await params;

  if (!stakeholderRoles.includes(role as StakeholderRole)) {
    return NextResponse.json({ error: "Unsupported role." }, { status: 404 });
  }

  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const table = roleTableMap[role as StakeholderRole];
  const { data, error } = await auth.supabase
    .from(table)
    .select("*")
    .eq("owner_id", auth.user.id)
    .neq("status", "inactive")
    .order("created_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json((data ?? []).map((row) => ({ ...row, role }))); 
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ role: string }> }
) {
  const { role } = await params;

  if (!stakeholderRoles.includes(role as StakeholderRole)) {
    return NextResponse.json({ error: "Unsupported role." }, { status: 404 });
  }

  const auth = await getAuthenticatedClient({ redirectOnFail: false });

  if (!auth) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as StakeholderInput;

  if (!payload.name?.trim()) {
    return NextResponse.json({ error: "Name is required." }, { status: 400 });
  }

  const table = roleTableMap[role as StakeholderRole];
  const sanitizedPayload = sanitizeStakeholderPayload(role as StakeholderRole, payload);
  const { data, error } = await auth.supabase
    .from(table)
    .insert({
      id: crypto.randomUUID(),
      owner_id: auth.user.id,
      ...sanitizedPayload,
      name: payload.name.trim(),
    })
    .select("*")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json({ ...data, role }, { status: 201 });
}
