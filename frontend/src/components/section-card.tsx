import { ReactNode } from "react";

type Props = {
  title: string;
  description?: string;
  children: ReactNode;
};

export default function SectionCard({ title, description, children }: Props) {
  return (
    <section className="rounded-3xl border border-zinc-200/80 bg-white/90 p-5 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.28)] backdrop-blur">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-zinc-900">{title}</h2>
        {description ? (
          <p className="mt-1 text-sm leading-6 text-zinc-500">{description}</p>
        ) : null}
      </div>
      {children}
    </section>
  );
}
