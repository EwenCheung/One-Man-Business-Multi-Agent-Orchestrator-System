import RolePage from "@/components/roles/role-page";
import { getSuppliers } from "@/lib/api";
import type { StakeholderRow } from "@/lib/types";

export default async function SuppliersPage() {
  const data = await getSuppliers();

  return <RolePage role="suppliers" title="Suppliers" description="Supplier records and sourcing information." data={data.map((item) => ({ ...item, role: "suppliers" })) as StakeholderRow[]} />;
}
