type Props = {
  title: string;
  value: string;
  description: string;
};

export default function StatCard({ title, value, description }: Props) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-zinc-500">{title}</p>
      <p className="mt-3 text-3xl font-semibold text-zinc-900">{value}</p>
      <p className="mt-2 text-sm text-zinc-500">{description}</p>
    </div>
  );
}