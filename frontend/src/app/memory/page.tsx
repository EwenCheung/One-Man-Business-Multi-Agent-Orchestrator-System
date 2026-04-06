import MemoryClient from "@/components/memory/memory-client";
import { getMemoryOverview } from "@/lib/api";

export default async function MemoryPage() {
  const overview = await getMemoryOverview();

  return <MemoryClient initialData={overview} />;
}
