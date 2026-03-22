"use client";

import Link from "next/link";

export default function RolesLanding() {
  const roles = ["customers", "suppliers", "investors", "partners"];

  return (
    <main className="p-6">
      <h1 className="text-2xl font-bold mb-4">Role Explorer</h1>
      <div className="grid gap-4 md:grid-cols-2">
        {roles.map((role) => (
          <Link key={role} href={`/roles/${role}`} className="rounded-xl border p-4 hover:bg-gray-50">
            <h2 className="text-lg font-semibold capitalize">{role}</h2>
            <p className="text-gray-600 mt-1">View and manage this role context + data.</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
