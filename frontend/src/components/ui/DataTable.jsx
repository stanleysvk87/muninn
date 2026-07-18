import { useMemo, useState } from "react";

export default function DataTable({ columns, rows, onRowClick, rowKey = "id" }) {
  const [sort, setSort] = useState({ key: null, dir: 1 });

  const sorted = useMemo(() => {
    if (!sort.key) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sort.key] ?? "";
      const bv = b[sort.key] ?? "";
      if (av < bv) return -1 * sort.dir;
      if (av > bv) return 1 * sort.dir;
      return 0;
    });
  }, [rows, sort]);

  function toggleSort(key) {
    setSort((prev) => (prev.key === key ? { key, dir: -prev.dir } : { key, dir: 1 }));
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={col.key} onClick={() => col.sortable !== false && toggleSort(col.key)} style={{ cursor: col.sortable === false ? "default" : "pointer" }}>
              {col.label}
              {sort.key === col.key ? (sort.dir === 1 ? " ^" : " v") : ""}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row[rowKey]} onClick={() => onRowClick?.(row)}>
            {columns.map((col) => (
              <td key={col.key}>{col.render ? col.render(row) : row[col.key]}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
