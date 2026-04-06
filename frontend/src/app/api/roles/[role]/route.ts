import { getAuthenticatedClient } from "@/lib/api";
import { roleTableMap, stakeholderRoles, type StakeholderRole } from "@/lib/stakeholder-config";
import type { StakeholderInput } from "@/lib/types";
import { NextResponse } from "next/server";

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
  const { data, error } = await auth.supabase
    .from(table)
    .insert({
      id: crypto.randomUUID(),
      owner_id: auth.user.id,
      ...payload,
      name: payload.name.trim(),
    })
    .select("*")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json({ ...data, role }, { status: 201 });
}
