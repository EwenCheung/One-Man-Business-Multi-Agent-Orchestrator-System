import { customers } from "@/lib/mock-data";
import { NextResponse } from "next/server";

export async function GET(request: Request, { params }: { params: { role: string } }) {
  const { role } = params;

  if (role === "customers") {
    return NextResponse.json(customers);
  }

  const generic = [
    { id: "x1", name: `${role} A`, summary: `Sample ${role} record` },
    { id: "x2", name: `${role} B`, summary: `Sample ${role} record` },
  ];

  return NextResponse.json(generic);
}
