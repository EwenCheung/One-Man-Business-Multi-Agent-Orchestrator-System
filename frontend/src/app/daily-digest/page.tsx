import DailyDigestClient from "@/components/daily-digest/daily-digest-client";
import { getDailyDigestPayload } from "@/lib/api";

export default async function DailyDigestPage() {
  const digest = await getDailyDigestPayload();

  return <DailyDigestClient initialData={digest} />;
}
