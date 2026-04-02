import StakeholdersClient from "@/components/roles/stakeholders-client";
import type { StakeholderRole, StakeholderRow } from "@/lib/types";

export default function RolePage({
  role,
  title,
  description,
  data,
}: {
  role: StakeholderRole;
  title: string;
  description: string;
  data: StakeholderRow[];
}) {
  return <StakeholdersClient role={role} title={title} description={description} initialData={data} />;
}
