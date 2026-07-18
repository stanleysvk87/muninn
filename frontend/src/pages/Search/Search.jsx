import { useEffect, useMemo, useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button.jsx";
import DataTable from "../../components/ui/DataTable.jsx";
import EmptyState from "../../components/ui/EmptyState.jsx";
import ErrorState from "../../components/ui/ErrorState.jsx";
import LoadingBlock from "../../components/ui/LoadingBlock.jsx";
import PageHeader from "../../components/ui/PageHeader.jsx";
import StatusBadge from "../../components/ui/StatusBadge.jsx";
import { useI18n } from "../../i18n.jsx";

function Highlighted({ text }) {
  if (!text) return null;
  const parts = text.split(/(<<[^>]*>>)/g);
  return parts.map((part, i) => {
    const match = part.match(/^<<([^>]*)>>$/);
    return match ? <mark key={i}>{match[1]}</mark> : <span key={i}>{part}</span>;
  });
}

export default function Search({ expiringOnly = false, savedView = null, onOpenDocument, onNavigate }) {
  const { docTypeLabel, localizedSummary, savedViewLabel, t } = useI18n();
  const [q, setQ] = useState("");
  const [correspondent, setCorrespondent] = useState(null);
  const [docType, setDocType] = useState(null);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [facets, setFacets] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [filtersOpen, setFiltersOpen] = useState(false);

  const columns = useMemo(() => [
    { key: "correspondent", label: t("table.correspondent") },
    { key: "doc_type", label: t("table.type"), render: (r) => docTypeLabel(r.doc_type) },
    { key: "doc_date", label: t("table.date") },
    { key: "expiry_date", label: t("table.validUntil"), hideOnMobile: true, render: (r) => r.expiry_date || "-" },
    {
      key: "amount_value",
      label: t("table.amount"),
      hideOnMobile: true,
      render: (r) => (r.amount_value != null ? `${r.amount_value} ${r.amount_currency || ""}` : "-"),
    },
    { key: "status", label: t("table.status"), sortable: false, render: (r) => <StatusBadge status={r.status} /> },
    {
      key: "summary",
      label: t("table.summary"),
      sortable: false,
      hideOnMobile: true,
      render: (r) => (
        <span style={{ color: "var(--color-text-secondary)" }}>
          {r.match_snippet ? <Highlighted text={r.match_snippet} /> : localizedSummary(r).slice(0, 80)}
        </span>
      ),
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
            {t("common.download")}
          </a>
        ) : null,
    },
  ], [t]);

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
      .catch((err) => !cancelled && setError(err.response?.data?.detail || t("search.loadFailed")));
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
    if (!window.confirm(t("search.deleteConfirm", { count: selected.size }))) return;
    await api.delete("/documents", { params: { ids: [...selected].join(",") } });
    setSelected(new Set());
    setRows((prev) => prev.filter((r) => !selected.has(r.id)));
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("search.eyebrow")}
        title={expiringOnly ? t("search.expirations") : savedView ? savedViewLabel(savedView, t("search.view")) : t("search.title")}
        description={
          expiringOnly
            ? t("search.expiringDescription")
            : savedView
              ? t("search.savedViewDescription")
              : t("search.description")
        }
        actions={(expiringOnly || savedView) ? <Button variant="secondary" onClick={() => onNavigate("search")}>{t("search.allDocuments")}</Button> : null}
      />
      {!expiringOnly && !savedView && (
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("search.placeholder")}
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
              {t("search.filters")}
            </Button>
            {(docType || correspondent) && (
              <Button
                variant="ghost"
                onClick={() => {
                  setDocType(null);
                  setCorrespondent(null);
                }}
              >
                {t("search.clearFilters")}
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
              {docTypeLabel(f.doc_type)} ({f.count})
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
          <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>{t("search.selected", { count: selected.size })}</span>
          <a className="btn btn-secondary" href={`/api/documents/export?format=zip&ids=${[...selected].join(",")}`}>
            {t("search.downloadZip")}
          </a>
          <Button variant="ghost" onClick={bulkDelete}>
            {t("search.deleteSelected")}
          </Button>
        </div>
      )}

      {error && <ErrorState>{error}</ErrorState>}
      {!error && rows === null && <LoadingBlock />}
      {!error && rows && rows.length === 0 && <EmptyState>{t("search.empty")}</EmptyState>}
      {!error && rows && rows.length > 0 && (
        <DataTable
          columns={columns}
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
                aria-label={t("search.selectDocument", { name: row.original_filename || row.correspondent })}
              />
              <div className="mobile-doc-main">
                <strong>{row.correspondent}</strong>
                <span>{docTypeLabel(row.doc_type)}{row.expiry_date ? ` · ${t("search.validUntil", { date: row.expiry_date })}` : row.doc_date ? ` · ${row.doc_date}` : ""}</span>
                {row.match_snippet ? <p><Highlighted text={row.match_snippet} /></p> : localizedSummary(row) && <p>{localizedSummary(row).slice(0, 120)}</p>}
              </div>
              <div className="mobile-doc-actions" onClick={(e) => e.stopPropagation()}>
                <StatusBadge status={row.status} />
                {row.status === "processed" && (
                  <a className="btn btn-ghost" href={`/api/documents/${row.id}/file?download=true`}>
                    {t("common.download")}
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
