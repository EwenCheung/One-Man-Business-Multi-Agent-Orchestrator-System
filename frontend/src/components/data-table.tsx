import { TableColumn } from "@/lib/types";

type DataTableProps<T extends Record<string, unknown>> = {
  columns: TableColumn<T>[];
  data: T[];
};

function renderCellValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  return String(value);
}

export default function DataTable<T extends Record<string, unknown>>({
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
                    {column.render
                      ? column.render(
                          column.key in row ? row[column.key as keyof T] : undefined,
                          row
                        )
                      : renderCellValue(
                          column.key in row ? row[column.key as keyof T] : undefined
                        )}
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
