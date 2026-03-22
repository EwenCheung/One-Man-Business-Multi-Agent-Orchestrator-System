import { useState } from "react";

const longTerm = [
  {
    id: "m1",
    title: "Owner rules",
    content: "Only answer with policy-safe and triple-checked business info.",
  },
];

const grepMemory = [
  {
    id: "m2",
    title: "Customer preference summary",
    content: "Customer A likes bulk discount and direct negotiation.",
  },
];

const shortTerm = [
  {
    id: "m3",
    title: "Recent Chat",
    content: "Latest conversation question: 'Can you offer an aggregated supplier quote?'.",
  },
];

export default function MemoryPage() {
  const [layer, setLayer] = useState<"long" | "grep" | "short">("long");
  const data = layer === "long" ? longTerm : layer === "grep" ? grepMemory : shortTerm;

  return (
    <main className="p-6">
      <h1 className="text-2xl font-bold mb-4">Memory Hub</h1>

      <div className="mb-6 flex gap-2">
        <button
          onClick={() => setLayer("long")}
          className={`rounded-lg px-3 py-2 ${layer === "long" ? "bg-blue-500 text-white" : "bg-gray-100"}`}
        >
          Long-term
        </button>
        <button
          onClick={() => setLayer("grep")}
          className={`rounded-lg px-3 py-2 ${layer === "grep" ? "bg-blue-500 text-white" : "bg-gray-100"}`}
        >
          Grep Layer
        </button>
        <button
          onClick={() => setLayer("short")}
          className={`rounded-lg px-3 py-2 ${layer === "short" ? "bg-blue-500 text-white" : "bg-gray-100"}`}
        >
          Short-term
        </button>
      </div>

      <div className="space-y-4">
        {data.map((item) => (
          <article key={item.id} className="rounded-xl border p-4">
            <h2 className="font-semibold">{item.title}</h2>
            <p className="text-gray-700 mt-1">{item.content}</p>
          </article>
        ))}
      </div>
    </main>
  );
}
