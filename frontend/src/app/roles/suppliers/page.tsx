import DataTable from "@/components/data-table";
import { getSuppliers } from "@/lib/api";
import { SupplierRow } from "@/lib/types";

export default async function SuppliersPage() {
  const data = await getSuppliers();

  const columns: { key: keyof SupplierRow; label: string }[] = [
    { key: "id", label: "Supplier ID" },
    { key: "company", label: "Company" },
    { key: "supplyPrice", label: "Supply Price" },
    { key: "stock", label: "Stock" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Suppliers</h1>
        <p className="mt-2 text-zinc-500">
          Supplier details, stock information, and supply pricing.
        </p>
      </div>

      <DataTable columns={columns} data={data} />
    </div>
  );
}