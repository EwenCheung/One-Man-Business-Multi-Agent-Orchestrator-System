import RolePage from "@/components/roles/role-page";
import { getCustomers } from "@/lib/api";
import type { StakeholderRow } from "@/lib/types";

export default async function CustomersPage() {
  const data = await getCustomers();

  return <RolePage role="customers" title="Customers" description="Customer contacts and business profile information." data={data.map((item) => ({ ...item, role: "customers" })) as StakeholderRow[]} />;
}
