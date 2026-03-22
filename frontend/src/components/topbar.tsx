export default function Topbar() {
  return (
    <div className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-4">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900">Owner Dashboard</h1>
        <p className="text-sm text-zinc-500">
          Review updates, monitor roles, and manage approvals.
        </p>
      </div>

      <div className="rounded-full border border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-700">
        Owner View
      </div>
    </div>
  );
}