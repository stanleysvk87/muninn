import { useEffect, useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button.jsx";
import DataTable from "../../components/ui/DataTable.jsx";
import EmptyState from "../../components/ui/EmptyState.jsx";
import ErrorState from "../../components/ui/ErrorState.jsx";
import LoadingBlock from "../../components/ui/LoadingBlock.jsx";
import PageHeader from "../../components/ui/PageHeader.jsx";
import StatusBadge from "../../components/ui/StatusBadge.jsx";

const COLUMNS = [
  { key: "correspondent", label: "Firma / osoba" },
  { key: "doc_type", label: "Typ" },
  { key: "doc_date", label: "Datum" },
  {
    key: "amount_value",
    label: "Suma",
    hideOnMobile: true,
    render: (r) => (r.amount_value != null ? `${r.amount_value} ${r.amount_currency || ""}` : "-"),
  },
  { key: "status", label: "Stav", sortable: false, render: (r) => <StatusBadge status={r.status} /> },
  {
    key: "summary",
    label: "Zhrnutie",
    sortable: false,
    hideOnMobile: true,
    render: (r) => <span style={{ color: "var(--color-text-secondary)" }}>{(r.summary || "").slice(0, 80)}</span>,
  },
  {
    key: "actions",
    label: "",
    sortable: false,
    render: (r) =>
      r.status === "processed" ? (
        <a
          className="btn btn-ghost"
          href={`/api/documents/${r.id}/file?download=true`}
          onClick={(e) => e.stopPropagation()}
          style={{ padding: "4px 10px", minHeight: "auto" }}
        >
          Stiahnut
        </a>
      ) : null,
  },
];

export default function Search({ onOpenDocument }) {
  const [q, setQ] = useState("");
  const [correspondent, setCorrespondent] = useState(null);
  const [docType, setDocType] = useState(null);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [facets, setFacets] = useState(null);
  const [selected, setSelected] = useState(new Set());

  useEffect(() => {
    api.get("/documents/facets").then((res) => setFacets(res.data));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = {};
    if (q) params.q = q;
    if (correspondent) params.correspondent = correspondent;
    if (docType) params.doc_type = docType;
    api
      .get("/documents", { params })
      .then((res) => !cancelled && setRows(res.data))
      .catch((err) => !cancelled && setError(err.response?.data?.detail || "Nepodarilo sa nacitat dokumenty"));
    return () => {
      cancelled = true;
    };
  }, [q, correspondent, docType]);

  useEffect(() => {
    setSelected(new Set());
  }, [q, correspondent, docType]);

  function toggleSelect(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(checked) {
    setSelected(checked ? new Set(rows.map((r) => r.id)) : new Set());
  }

  async function bulkDelete() {
    if (!window.confirm(`Naozaj zmazat ${selected.size} vybranych dokumentov?`)) return;
    await api.delete("/documents", { params: { ids: [...selected].join(",") } });
    setSelected(new Set());
    setRows((prev) => prev.filter((r) => !selected.has(r.id)));
  }

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
          marginBottom: 12,
          borderRadius: 8,
          border: "1px solid var(--color-border-strong)",
          background: "var(--color-ink-secondary)",
          color: "var(--color-text-primary)",
        }}
      />

      {facets && (facets.correspondents.length > 0 || facets.doc_types.length > 0) && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          {facets.doc_types.map((f) => (
            <button
              key={`type-${f.doc_type}`}
              className="status-badge"
              onClick={() => setDocType(docType === f.doc_type ? null : f.doc_type)}
              style={{
                cursor: "pointer",
                borderColor: docType === f.doc_type ? "var(--color-blue-light)" : undefined,
                color: docType === f.doc_type ? "var(--color-blue-light)" : undefined,
              }}
            >
              {f.doc_type} ({f.count})
            </button>
          ))}
          {facets.correspondents.slice(0, 12).map((f) => (
            <button
              key={`corr-${f.correspondent}`}
              className="status-badge"
              onClick={() => setCorrespondent(correspondent === f.correspondent ? null : f.correspondent)}
              style={{
                cursor: "pointer",
                borderColor: correspondent === f.correspondent ? "var(--color-blue-light)" : undefined,
                color: correspondent === f.correspondent ? "var(--color-blue-light)" : undefined,
              }}
            >
              {f.correspondent} ({f.count})
            </button>
          ))}
        </div>
      )}

      {selected.size > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, padding: "8px 16px", background: "var(--color-panel)", border: "1px solid var(--color-border)", borderRadius: 8 }}>
          <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>{selected.size} oznacenych</span>
          <a className="btn btn-secondary" href={`/api/documents/export?format=zip&ids=${[...selected].join(",")}`}>
            Stiahnut ako ZIP
          </a>
          <Button variant="ghost" onClick={bulkDelete}>
            Zmazat oznacene
          </Button>
        </div>
      )}

      {error && <ErrorState>{error}</ErrorState>}
      {!error && rows === null && <LoadingBlock />}
      {!error && rows && rows.length === 0 && <EmptyState>Ziadne dokumenty</EmptyState>}
      {!error && rows && rows.length > 0 && (
        <DataTable
          columns={COLUMNS}
          rows={rows}
          onRowClick={(row) => onOpenDocument(row.id)}
          selectable
          selectedIds={selected}
          onToggleSelect={toggleSelect}
          onToggleAll={toggleAll}
        />
      )}
    </div>
  );
}
