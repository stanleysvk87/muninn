import { useMemo, useState } from "react";

export default function DataTable({
  columns,
  rows,
  onRowClick,
  rowKey = "id",
  selectable = false,
  selectedIds,
  onToggleSelect,
  onToggleAll,
  mobileRender,
}) {
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

  const allSelected = selectable && rows.length > 0 && rows.every((r) => selectedIds?.has(r[rowKey]));

  return (
    <>
      {mobileRender && (
        <div className="mobile-data-list">
          {sorted.map((row) => mobileRender(row, {
            selected: selectedIds?.has(row[rowKey]) ?? false,
            toggleSelected: () => onToggleSelect?.(row[rowKey]),
            open: () => onRowClick?.(row),
          }))}
        </div>
      )}
      <div className="data-table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              {selectable && (
                <th style={{ width: 32 }}>
                  <input type="checkbox" checked={allSelected} onChange={(e) => onToggleAll?.(e.target.checked)} />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={col.hideOnMobile ? "hide-mobile" : ""}
                  onClick={() => col.sortable !== false && toggleSort(col.key)}
                  style={{ cursor: col.sortable === false ? "default" : "pointer" }}
                >
                  {col.label}
                  {sort.key === col.key ? (sort.dir === 1 ? " ^" : " v") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row[rowKey]} onClick={() => onRowClick?.(row)}>
                {selectable && (
                  <td onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds?.has(row[rowKey]) ?? false}
                      onChange={() => onToggleSelect?.(row[rowKey])}
                    />
                  </td>
                )}
                {columns.map((col) => (
                  <td key={col.key} className={col.hideOnMobile ? "hide-mobile" : ""}>
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
