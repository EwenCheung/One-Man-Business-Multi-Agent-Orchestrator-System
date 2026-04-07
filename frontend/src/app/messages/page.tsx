import MessagesClient from "@/components/messages/messages-client";

export default async function MessagesPage({
  searchParams,
}: {
  searchParams: Promise<{ threadId?: string }>;
}) {
  const params = await searchParams;

  return <MessagesClient initialThreadId={params.threadId ?? null} />;
}
