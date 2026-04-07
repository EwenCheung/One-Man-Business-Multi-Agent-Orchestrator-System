import RolePage from "@/components/roles/role-page";
import { getPartners } from "@/lib/api";
import type { StakeholderRow } from "@/lib/types";

export default async function PartnersPage() {
  const data = await getPartners();

  return <RolePage role="partners" title="Partners" description="Partner records and collaboration information." data={data.map((item) => ({ ...item, role: "partners" })) as StakeholderRow[]} />;
}
