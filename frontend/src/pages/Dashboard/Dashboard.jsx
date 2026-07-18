import { useEffect, useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button.jsx";
import Card from "../../components/ui/Card.jsx";
import EmptyState from "../../components/ui/EmptyState.jsx";
import PageHeader from "../../components/ui/PageHeader.jsx";
import StatusBadge from "../../components/ui/StatusBadge.jsx";

function daysUntil(dateStr) {
  const diffMs = new Date(dateStr) - new Date(new Date().toDateString());
  return Math.round(diffMs / (1000 * 60 * 60 * 24));
}

export default function Dashboard({ onOpenDocument, onNavigate }) {
  const [recent, setRecent] = useState(null);
  const [facets, setFacets] = useState(null);
  const [expiring, setExpiring] = useState(null);

  useEffect(() => {
    api.get("/documents", { params: { limit: 8 } }).then((res) => setRecent(res.data));
    api.get("/documents/facets").then((res) => setFacets(res.data));
    api.get("/documents/expiring").then((res) => setExpiring(res.data));
  }, []);

  const totalDocs = facets ? facets.correspondents.reduce((sum, c) => sum + c.count, 0) : null;
  const totalCorrespondents = facets ? facets.correspondents.length : null;
  const failedCount = facets ? facets.failed_count : 0;
  const expiringCount = expiring ? expiring.length : 0;

  return (
    <div>
      <PageHeader
        eyebrow="Muninn"
        title="Prehlad"
        description="Rychly pohlad na archiv a rychle akcie."
        actions={
          <>
            <Button variant="secondary" onClick={() => onNavigate("search")}>
              Hladat
            </Button>
            <Button onClick={() => onNavigate("upload")}>Nahrat dokument</Button>
          </>
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16, marginBottom: 24 }}>
        <Card>
          <div className="eyebrow">Dokumentov</div>
          <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6 }}>{totalDocs ?? "-"}</div>
        </Card>
        <Card>
          <div className="eyebrow">Firiem / osob</div>
          <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6 }}>{totalCorrespondents ?? "-"}</div>
        </Card>
        {failedCount > 0 && (
          <Card hover onClick={() => onNavigate("search")} style={{ cursor: "pointer", borderColor: "var(--color-warning)" }}>
            <div className="eyebrow" style={{ color: "var(--color-warning)" }}>Zlyhalo spracovanie</div>
            <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6, color: "var(--color-warning)" }}>{failedCount}</div>
          </Card>
        )}
        {expiringCount > 0 && (
          <Card hover onClick={() => onNavigate("search")} style={{ cursor: "pointer", borderColor: "var(--color-gold)" }}>
            <div className="eyebrow" style={{ color: "var(--color-gold)" }}>Blizi sa expiracia</div>
            <div style={{ fontSize: 32, fontFamily: "var(--font-display)", marginTop: 6, color: "var(--color-gold)" }}>{expiringCount}</div>
          </Card>
        )}
      </div>

      {expiringCount > 0 && (
        <>
          <h3 style={{ marginBottom: 12 }}>Blizi sa expiracia</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
            {expiring.map((doc) => {
              const days = daysUntil(doc.expiry_date);
              const overdue = days < 0;
              return (
                <Card
                  key={doc.id}
                  hover
                  onClick={() => onOpenDocument(doc.id)}
                  style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", padding: 16 }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{doc.correspondent}</div>
                    <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
                      {doc.doc_type} · plati do {doc.expiry_date}
                    </div>
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      fontFamily: "var(--font-mono)",
                      color: overdue ? "var(--color-warning)" : "var(--color-gold)",
                    }}
                  >
                    {overdue ? `po termine ${Math.abs(days)} dni` : `o ${days} dni`}
                  </div>
                </Card>
              );
            })}
          </div>
        </>
      )}

      <h3 style={{ marginBottom: 12 }}>Naposledy pridane</h3>
      {recent === null && <div style={{ color: "var(--color-text-secondary)" }}>Nacitavam...</div>}
      {recent && recent.length === 0 && (
        <EmptyState>
          Zatial tu nic nie je. <a href="#" onClick={(e) => { e.preventDefault(); onNavigate("upload"); }}>Nahraj prvy dokument</a>.
        </EmptyState>
      )}
      {recent && recent.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {recent.map((doc) => (
            <Card key={doc.id} hover onClick={() => onOpenDocument(doc.id)} style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", padding: 16 }}>
              <div>
                <div style={{ fontWeight: 600 }}>{doc.correspondent}</div>
                <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
                  {doc.doc_type} {doc.doc_date ? `· ${doc.doc_date}` : ""}
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
