import { TableColumn } from "@/lib/types";

type DataTableProps<T extends Record<string, string>> = {
  columns: TableColumn<T>[];
  data: T[];
};

export default function DataTable<T extends Record<string, string>>({
  columns,
  data,
}: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left">
          <thead className="bg-zinc-50">
            <tr>
              {columns.map((column) => (
                <th
                  key={String(column.key)}
                  className="px-5 py-4 text-sm font-semibold text-zinc-700"
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, index) => (
              <tr
                key={index}
                className="border-t border-zinc-200 last:border-b-0"
              >
                {columns.map((column) => (
                  <td
                    key={String(column.key)}
                    className="px-5 py-4 text-sm text-zinc-700"
                  >
                    {row[column.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}