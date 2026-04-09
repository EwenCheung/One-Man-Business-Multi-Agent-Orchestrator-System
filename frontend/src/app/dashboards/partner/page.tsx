import { getAuthenticatedClient } from "@/lib/api";
import { createAdminClient } from "@/lib/supabase/admin";
import { redirect } from "next/navigation";

type PartnerAgreementRow = {
  description: string | null;
  agreement_type: string | null;
  revenue_share_pct: number | null;
  end_date: string | null;
  is_active: boolean | null;
  notes: string | null;
};

export default async function PartnerDashboardPage() {
  const auth = await getAuthenticatedClient();
  if (!auth) redirect("/login");
  
  if (auth.user.user_metadata?.role !== "partner") {
    return <p className="p-8 text-red-600">Unauthorized. You are not a partner.</p>;
  }

  const { user } = auth;
  const admin = createAdminClient();
  
  const { data: partnerData } = await admin
    .from("partners")
    .select("id, owner_id")
    .or([user.email ? `email.eq.${user.email}` : null, user.phone ? `phone.eq.${user.phone}` : null].filter(Boolean).join(","))
    .single();

  let agreements: PartnerAgreementRow[] = [];
  if (partnerData) {
    const { data: agreementData } = await admin
      .from("partner_agreements")
      .select("description, agreement_type, revenue_share_pct, end_date, is_active, notes")
      .eq("owner_id", partnerData.owner_id)
      .eq("partner_id", partnerData.id);
    agreements = agreementData || [];
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto py-8 px-4">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Partner Dashboard</h1>
        <p className="mt-2 text-zinc-500">View your active partner agreements and performance details.</p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm text-zinc-600">
          <thead className="bg-zinc-50 font-medium text-zinc-900">
            <tr>
              <th className="px-6 py-4">Agreement Type</th>
              <th className="px-6 py-4">Description</th>
              <th className="px-6 py-4">Revenue Share</th>
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4">End Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {agreements.map((a, i) => (
              <tr key={i} className="hover:bg-zinc-50/50">
                <td className="px-6 py-4 font-medium text-zinc-900">{a.agreement_type}</td>
                <td className="px-6 py-4">{a.description}</td>
                <td className="px-6 py-4">{a.revenue_share_pct}%</td>
                <td className="px-6 py-4">
                  <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                    a.is_active ? 'bg-green-50 text-green-700 ring-1 ring-inset ring-green-600/20' : 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20'
                  }`}>
                    {a.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4">{a.end_date?.split("T")[0]}</td>
              </tr>
            ))}
            {agreements.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-zinc-500">No active partner agreements found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
