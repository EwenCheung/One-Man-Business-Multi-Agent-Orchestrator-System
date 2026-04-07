import DailyDigestClient from "@/components/daily-digest/daily-digest-client";
import { getDailyDigest } from "@/lib/api";

export default async function DailyDigestPage() {
  const digest = await getDailyDigest();

  return <DailyDigestClient initialData={digest} />;
}
