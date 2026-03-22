import DataTable from "@/components/data-table";
import { getPartners } from "@/lib/api";
import { PartnerRow } from "@/lib/types";

export default async function PartnersPage() {
  const data = await getPartners();

  const columns: { key: keyof PartnerRow; label: string }[] = [
    { key: "id", label: "Partner ID" },
    { key: "name", label: "Name" },
    { key: "partnershipType", label: "Partnership Type" },
    { key: "status", label: "Status" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Partners</h1>
        <p className="mt-2 text-zinc-500">
          Partnership summaries, status, and collaboration type.
        </p>
      </div>

      <DataTable columns={columns} data={data} />
    </div>
  );
}