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
  { key: "expiry_date", label: "Plati do", hideOnMobile: true, render: (r) => r.expiry_date || "-" },
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

const SAVED_VIEW_LABELS = {
  review: "Na kontrolu",
  pay: "Zaplatit",
  failed: "Zlyhania",
  duplicates: "Mozne duplikaty",
};

export default function Search({ expiringOnly = false, savedView = null, onOpenDocument, onNavigate }) {
  const [q, setQ] = useState("");
  const [correspondent, setCorrespondent] = useState(null);
  const [docType, setDocType] = useState(null);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [facets, setFacets] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    api.get("/documents/facets").then((res) => setFacets(res.data));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = {};
    if (q) params.q = q;
    if (correspondent && !savedView) params.correspondent = correspondent;
    if (docType && !savedView) params.doc_type = docType;
    if (savedView) params.saved_view = savedView;
    const request = expiringOnly
      ? api.get("/documents/expiring")
      : api.get("/documents", { params });
    request
      .then((res) => !cancelled && setRows(res.data))
      .catch((err) => !cancelled && setError(err.response?.data?.detail || "Nepodarilo sa nacitat dokumenty"));
    return () => {
      cancelled = true;
    };
  }, [q, correspondent, docType, expiringOnly, savedView]);

  useEffect(() => {
    setSelected(new Set());
  }, [q, correspondent, docType, expiringOnly, savedView]);

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
      <PageHeader
        eyebrow="Archiv"
        title={expiringOnly ? "Expiracie" : savedView ? SAVED_VIEW_LABELS[savedView] || "Pohlad" : "Hladanie"}
        description={
          expiringOnly
            ? "Aktivne upozornenia, ktore este nie su oznacene ako vybavene."
            : savedView
              ? "Ulozeny pracovny pohlad z dashboardu."
              : "Zadaj meno firmy alebo cast textu (napr. 'uniqa')."
        }
        actions={(expiringOnly || savedView) ? <Button variant="secondary" onClick={() => onNavigate("search")}>Vsetky dokumenty</Button> : null}
      />
      {!expiringOnly && !savedView && (
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
      )}

      {!expiringOnly && !savedView && facets && (facets.correspondents.length > 0 || facets.doc_types.length > 0) && (
        <>
          <div className="filter-toolbar">
            <Button variant="secondary" onClick={() => setFiltersOpen((v) => !v)}>
              Filtre
            </Button>
            {(docType || correspondent) && (
              <Button
                variant="ghost"
                onClick={() => {
                  setDocType(null);
                  setCorrespondent(null);
                }}
              >
                Zrusit filtre
              </Button>
            )}
          </div>
          <div className={`filter-chips ${filtersOpen ? "open" : ""}`}>
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
        </>
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
          mobileRender={(row, state) => (
            <div key={row.id} className="mobile-doc-row" onClick={state.open}>
              <input
                type="checkbox"
                checked={state.selected}
                onClick={(e) => e.stopPropagation()}
                onChange={state.toggleSelected}
                aria-label={`Oznacit dokument ${row.original_filename || row.correspondent}`}
              />
              <div className="mobile-doc-main">
                <strong>{row.correspondent}</strong>
                <span>{row.doc_type || "-"}{row.expiry_date ? ` · plati do ${row.expiry_date}` : row.doc_date ? ` · ${row.doc_date}` : ""}</span>
                {row.summary && <p>{row.summary.slice(0, 120)}</p>}
              </div>
              <div className="mobile-doc-actions" onClick={(e) => e.stopPropagation()}>
                <StatusBadge status={row.status} />
                {row.status === "processed" && (
                  <a className="btn btn-ghost" href={`/api/documents/${row.id}/file?download=true`}>
                    Stiahnut
                  </a>
                )}
              </div>
            </div>
          )}
        />
      )}
    </div>
  );
}
