import { getAuthenticatedClient } from "@/lib/api";
import { createAdminClient } from "@/lib/supabase/admin";
import { redirect } from "next/navigation";

type SupplierContractRow = {
  supply_price: number | null;
  stock_we_buy: number | null;
  contract_start: string | null;
  contract_end: string | null;
  products: { name: string; description: string | null; stock_number: number | null } | { name: string; description: string | null; stock_number: number | null }[] | null;
};

export default async function SupplierDashboardPage() {
  const auth = await getAuthenticatedClient();
  if (!auth) redirect("/login");
  
  if (auth.user.user_metadata?.role !== "supplier") {
    return <p className="p-8 text-red-600">Unauthorized. You are not a supplier.</p>;
  }

  const { user } = auth;
  const admin = createAdminClient();
  
  const { data: supplierData } = await admin
    .from("suppliers")
    .select("id, owner_id")
    .or([user.email ? `email.eq.${user.email}` : null, user.phone ? `phone.eq.${user.phone}` : null].filter(Boolean).join(","))
    .single();

  let contracts: SupplierContractRow[] = [];
  if (supplierData) {
    const { data: contractData } = await admin
      .from("supplier_products")
      .select("supply_price, stock_we_buy, contract_start, contract_end, products(name, description, stock_number)")
      .eq("owner_id", supplierData.owner_id)
      .eq("supplier_id", supplierData.id);
    contracts = contractData || [];
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto py-8 px-4">
      <div>
        <h1 className="text-3xl font-semibold text-zinc-900">Supplier Dashboard</h1>
        <p className="mt-2 text-zinc-500">View your active supply contracts and product statuses.</p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm text-zinc-600">
          <thead className="bg-zinc-50 font-medium text-zinc-900">
            <tr>
              <th className="px-6 py-4">Product Name</th>
              <th className="px-6 py-4">Supply Price</th>
              <th className="px-6 py-4">Stock Requested</th>
              <th className="px-6 py-4">Current Stock</th>
              <th className="px-6 py-4">Contract End</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {contracts.map((c, i) => {
              const product = Array.isArray(c.products) ? c.products[0] : c.products;
              return (
                <tr key={i} className="hover:bg-zinc-50/50">
                  <td className="px-6 py-4 font-medium text-zinc-900">{product?.name || "Unknown"}</td>
                  <td className="px-6 py-4">${c.supply_price}</td>
                  <td className="px-6 py-4">{c.stock_we_buy}</td>
                  <td className="px-6 py-4">{product?.stock_number || 0}</td>
                  <td className="px-6 py-4">{c.contract_end?.split("T")[0]}</td>
                </tr>
              )
            })}
            {contracts.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-zinc-500">No active supply contracts found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
