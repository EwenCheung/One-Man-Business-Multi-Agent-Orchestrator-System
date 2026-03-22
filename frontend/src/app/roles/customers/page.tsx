import DataTable from "@/components/data-table";
import { getCustomers } from "@/lib/api";
import { CustomerRow } from "@/lib/types";

export default async function CustomersPage() {
  const data = await getCustomers();

  const columns: { key: keyof CustomerRow; label: string }[] = [
    { key: "id", label: "Customer ID" },
    { key: "name", label: "Name" },
    { key: "preference", label: "Preference" },
    { key: "lastInteraction", label: "Last Interaction" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Customers</h1>
        <p className="mt-2 text-zinc-500">
          Customer-facing summary data and recent preferences.
        </p>
      </div>

      <DataTable columns={columns} data={data} />
    </div>
  );
}