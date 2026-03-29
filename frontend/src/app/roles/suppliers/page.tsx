import DataTable from "@/components/data-table";
import { getSuppliers } from "@/lib/api";

type SupplierRow = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  category: string | null;
  status: string | null;
};

export default async function SuppliersPage() {
  const data = await getSuppliers();

  const columns: { key: keyof SupplierRow; label: string }[] = [
    { key: "id", label: "Supplier ID" },
    { key: "name", label: "Name" },
    { key: "email", label: "Email" },
    { key: "category", label: "Category" },
    { key: "status", label: "Status" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Suppliers</h1>
        <p className="mt-2 text-zinc-500">
          Supplier records and sourcing information.
        </p>
      </div>

      <DataTable columns={columns} data={data} />
    </div>
  );
}