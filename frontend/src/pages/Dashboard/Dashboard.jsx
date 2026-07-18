import { useEffect, useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button.jsx";
import Card from "../../components/ui/Card.jsx";
import EmptyState from "../../components/ui/EmptyState.jsx";
import PageHeader from "../../components/ui/PageHeader.jsx";
import StatusBadge from "../../components/ui/StatusBadge.jsx";
import { useI18n } from "../../i18n.jsx";

function daysUntil(dateStr) {
  const diffMs = new Date(dateStr) - new Date(new Date().toDateString());
  return Math.round(diffMs / (1000 * 60 * 60 * 24));
}

export default function Dashboard({ onOpenDocument, onNavigate }) {
  const { dayUnit, docTypeLabel, savedViewDescription, savedViewLabel, t } = useI18n();
  const [recent, setRecent] = useState(null);
  const [facets, setFacets] = useState(null);
  const [expiring, setExpiring] = useState(null);
  const [savedViews, setSavedViews] = useState(null);

  useEffect(() => {
    api.get("/documents", { params: { limit: 8 } }).then((res) => setRecent(res.data));
    api.get("/documents/facets").then((res) => setFacets(res.data));
    api.get("/documents/expiring").then((res) => setExpiring(res.data));
    api.get("/documents/saved-views").then((res) => setSavedViews(res.data));
  }, []);

  async function dismissExpiry(docId) {
    await api.post(`/documents/${docId}/expiry-dismissal`);
    setExpiring((items) => (items || []).filter((doc) => doc.id !== docId));
  }

  const totalDocs = facets ? facets.correspondents.reduce((sum, c) => sum + c.count, 0) : null;
  const totalCorrespondents = facets ? facets.correspondents.length : null;
  const failedCount = facets ? facets.failed_count : 0;
  const pendingCount = facets ? facets.pending_count : 0;
  const expiringCount = expiring ? expiring.length : 0;

  return (
    <div>
      <PageHeader
        eyebrow="Muninn"
        title={t("dashboard.title")}
        description={t("dashboard.description")}
        actions={
          <>
            <Button variant="secondary" onClick={() => onNavigate("search")}>
              {t("common.search")}
            </Button>
            <Button onClick={() => onNavigate("upload")}>{t("dashboard.uploadDocument")}</Button>
          </>
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16, marginBottom: 24 }}>
        <Card hover onClick={() => onNavigate("search")} style={{ cursor: "pointer" }}>
          <div className="eyebrow">{t("dashboard.documents")}</div>
          <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6 }}>{totalDocs ?? "-"}</div>
        </Card>
        <Card>
          <div className="eyebrow">{t("dashboard.correspondents")}</div>
          <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6 }}>{totalCorrespondents ?? "-"}</div>
        </Card>
        {failedCount > 0 && (
          <Card hover onClick={() => onNavigate("search")} style={{ cursor: "pointer", borderColor: "var(--color-warning)" }}>
            <div className="eyebrow" style={{ color: "var(--color-warning)" }}>{t("dashboard.failedProcessing")}</div>
            <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6, color: "var(--color-warning)" }}>{failedCount}</div>
          </Card>
        )}
        {pendingCount > 0 && (
          <Card hover onClick={() => onNavigate("search", null, "?view=pending")} style={{ cursor: "pointer" }}>
            <div className="eyebrow" style={{ color: "var(--color-text-secondary)" }}>{t("dashboard.pendingProcessing")}</div>
            <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6, color: "var(--color-text-secondary)" }}>{pendingCount}</div>
          </Card>
        )}
        {expiringCount > 0 && (
          <Card hover onClick={() => onNavigate("search", null, "?expiring=1")} style={{ cursor: "pointer", borderColor: "var(--color-gold)" }}>
            <div className="eyebrow" style={{ color: "var(--color-gold)" }}>{t("dashboard.expiringSoon")}</div>
            <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6, color: "var(--color-gold)" }}>{expiringCount}</div>
          </Card>
        )}
      </div>

      {expiringCount > 0 && (
        <>
          <h3 style={{ marginBottom: 12 }}>{t("dashboard.expiringSoon")}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
            {expiring.map((doc) => {
              const days = daysUntil(doc.expiry_date);
              const overdue = days < 0;
              return (
                <Card
                  key={doc.id}
                  hover
                  onClick={() => onOpenDocument(doc.id)}
                  className="expiring-card"
                  style={{ cursor: "pointer" }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{doc.correspondent}</div>
                    <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
                      {t("dashboard.validUntil", { type: docTypeLabel(doc.doc_type), date: doc.expiry_date })}
                    </div>
                  </div>
                  <div className="expiring-actions">
                    <div
                      style={{
                        fontSize: 13,
                        fontFamily: "var(--font-mono)",
                        color: overdue ? "var(--color-warning)" : "var(--color-gold)",
                      }}
                    >
                      {overdue
                        ? t("dashboard.overdue", { count: Math.abs(days), unit: dayUnit(Math.abs(days)) })
                        : t("dashboard.inDays", { count: days, unit: dayUnit(days) })}
                    </div>
                    <Button
                      variant="secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        dismissExpiry(doc.id);
                      }}
                    >
                      {t("dashboard.done")}
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        </>
      )}

      <h3 style={{ marginBottom: 12 }}>{t("dashboard.workViews")}</h3>
      <div className="saved-view-grid">
        {(savedViews || []).map((view) => (
          <Card
            key={view.key}
            hover
            onClick={() => onNavigate("search", null, view.key === "expiring" ? "?expiring=1" : `?view=${view.key}`)}
            className="saved-view-card"
            style={{ cursor: "pointer" }}
          >
            <div>
              <div className="eyebrow">{savedViewLabel(view.key, view.label)}</div>
              <p>{savedViewDescription(view.key, view.description)}</p>
            </div>
            <strong>{view.count}</strong>
          </Card>
        ))}
        {savedViews === null && <div style={{ color: "var(--color-text-secondary)" }}>{t("dashboard.loadingViews")}</div>}
      </div>

      <h3 style={{ marginBottom: 12 }}>{t("dashboard.recent")}</h3>
      {recent === null && <div style={{ color: "var(--color-text-secondary)" }}>{t("common.loading")}</div>}
      {recent && recent.length === 0 && (
        <EmptyState>
          {t("dashboard.empty")} <a href="#" onClick={(e) => { e.preventDefault(); onNavigate("upload"); }}>{t("dashboard.uploadFirst")}</a>.
        </EmptyState>
      )}
      {recent && recent.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {recent.map((doc) => (
            <Card key={doc.id} hover onClick={() => onOpenDocument(doc.id)} style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", padding: 16 }}>
              <div>
                <div style={{ fontWeight: 600 }}>{doc.correspondent}</div>
                <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
                  {docTypeLabel(doc.doc_type)} {doc.doc_date ? `· ${doc.doc_date}` : ""}
                </div>
              </div>
              <StatusBadge status={doc.status} />
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
