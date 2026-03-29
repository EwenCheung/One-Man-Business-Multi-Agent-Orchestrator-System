import DataTable from "@/components/data-table";
import { getInvestors } from "@/lib/api";

type InvestorRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  focus: string | null;
  status: string | null;
};

export default async function InvestorsPage() {
  const data = await getInvestors();

  const columns: { key: keyof InvestorRow; label: string }[] = [
    { key: "id", label: "Investor ID" },
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "focus", label: "Focus" },
    { key: "status", label: "Status" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Investors</h1>
        <p className="mt-2 text-zinc-500">
          Investor contacts and profile information.
        </p>
      </div>

      <DataTable columns={columns} data={data} />
    </div>
  );
}