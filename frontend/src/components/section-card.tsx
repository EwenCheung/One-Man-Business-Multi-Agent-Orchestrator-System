import { ReactNode } from "react";

type Props = {
  title: string;
  description?: string;
  children: ReactNode;
};

export default function SectionCard({ title, description, children }: Props) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-zinc-900">{title}</h2>
        {description ? (
          <p className="mt-1 text-sm text-zinc-500">{description}</p>
        ) : null}
      </div>
      {children}
    </section>
  );
}