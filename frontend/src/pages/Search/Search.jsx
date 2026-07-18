import { useEffect, useState } from "react";
import api from "../../api/client";
import DataTable from "../../components/ui/DataTable";
import EmptyState from "../../components/ui/EmptyState";
import ErrorState from "../../components/ui/ErrorState";
import LoadingBlock from "../../components/ui/LoadingBlock";
import PageHeader from "../../components/ui/PageHeader";
import StatusBadge from "../../components/ui/StatusBadge";

const COLUMNS = [
  { key: "correspondent", label: "Firma" },
  { key: "doc_type", label: "Typ" },
  { key: "doc_date", label: "Datum" },
  {
    key: "amount_value",
    label: "Suma",
    render: (r) => (r.amount_value != null ? `${r.amount_value} ${r.amount_currency || ""}` : "-"),
  },
  { key: "status", label: "Stav", sortable: false, render: (r) => <StatusBadge status={r.status} /> },
  {
    key: "summary",
    label: "Zhrnutie",
    sortable: false,
    render: (r) => <span style={{ color: "var(--color-text-secondary)" }}>{(r.summary || "").slice(0, 80)}</span>,
  },
];

export default function Search({ onOpenDocument }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get("/documents", { params: q ? { q } : {} })
      .then((res) => !cancelled && setRows(res.data))
      .catch((err) => !cancelled && setError(err.response?.data?.detail || "Nepodarilo sa nacitat dokumenty"));
    return () => {
      cancelled = true;
    };
  }, [q]);

  return (
    <div>
      <PageHeader eyebrow="Archiv" title="Hladanie" description="Zadaj meno firmy alebo cast textu (napr. 'uniqa')." />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Hladat..."
        style={{
          width: "100%",
          padding: "10px 14px",
          marginBottom: 16,
          borderRadius: 8,
          border: "1px solid var(--color-border-strong)",
          background: "var(--color-ink-secondary)",
          color: "var(--color-text-primary)",
        }}
      />
      {error && <ErrorState>{error}</ErrorState>}
      {!error && rows === null && <LoadingBlock />}
      {!error && rows && rows.length === 0 && <EmptyState>Ziadne dokumenty</EmptyState>}
      {!error && rows && rows.length > 0 && (
        <DataTable columns={COLUMNS} rows={rows} onRowClick={(row) => onOpenDocument(row.id)} />
      )}
    </div>
  );
}
