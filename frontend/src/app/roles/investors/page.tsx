import DataTable from "@/components/data-table";
import { getInvestors } from "@/lib/api";
import { InvestorRow } from "@/lib/types";

export default async function InvestorsPage() {
  const data = await getInvestors();

  const columns: { key: keyof InvestorRow; label: string }[] = [
    { key: "id", label: "Investor ID" },
    { key: "product", label: "Product" },
    { key: "roi", label: "ROI" },
    { key: "dailySales", label: "Daily Sales" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Investors</h1>
        <p className="mt-2 text-zinc-500">
          ROI-focused summary metrics and product performance.
        </p>
      </div>

      <DataTable columns={columns} data={data} />
    </div>
  );
}