import RolePage from "@/components/roles/role-page";
import { getInvestors } from "@/lib/api";
import type { StakeholderRow } from "@/lib/types";

export default async function InvestorsPage() {
  const data = await getInvestors();

  return <RolePage role="investors" title="Investors" description="Investor contacts and profile information." data={data.map((item) => ({ ...item, role: "investors" })) as StakeholderRow[]} />;
}
