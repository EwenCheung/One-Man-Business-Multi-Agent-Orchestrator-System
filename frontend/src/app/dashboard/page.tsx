import DashboardClient from "@/components/owner-dashboard/dashboard-client";
import { getDashboardPayload } from "@/lib/api";

export default async function DashboardPage() {
  const payload = await getDashboardPayload();

  return <DashboardClient initialData={payload} />;
}
