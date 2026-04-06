type Props = {
  title: string;
  value: string;
  description: string;
};

function accentClass(title: string) {
  if (title.toLowerCase().includes("low stock")) {
    return "border-amber-200 bg-amber-50/70 text-amber-900";
  }

  if (title.toLowerCase().includes("products") || title.toLowerCase().includes("units")) {
    return "border-emerald-200 bg-emerald-50/70 text-emerald-900";
  }

  if (title.toLowerCase().includes("approval")) {
    return "border-sky-200 bg-sky-50/70 text-sky-900";
  }

  return "border-violet-200 bg-violet-50/70 text-violet-900";
}

export default function StatCard({ title, value, description }: Props) {
  return (
    <div className={`rounded-3xl border p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${accentClass(title)}`}>
      <p className="text-sm font-semibold uppercase tracking-[0.14em] text-zinc-500">{title}</p>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
      <p className="mt-2 text-sm text-zinc-600">{description}</p>
    </div>
  );
}
