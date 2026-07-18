import { useEffect, useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import ErrorState from "../../components/ui/ErrorState";
import LoadingBlock from "../../components/ui/LoadingBlock";
import PageHeader from "../../components/ui/PageHeader";
import StatusBadge from "../../components/ui/StatusBadge";

const inputStyle = {
  padding: "8px 12px",
  borderRadius: 8,
  border: "1px solid var(--color-border-strong)",
  background: "var(--color-ink-secondary)",
  color: "var(--color-text-primary)",
};

const REVIEW_STATUSES = [
  { value: "na_kontrolu", label: "Na kontrolu" },
  { value: "zaplatit", label: "Zaplatit" },
  { value: "vybavene", label: "Vybavene" },
  { value: "zamietnute", label: "Zamietnute" },
  { value: "archiv", label: "Archiv" },
];

const RECURRENCE_OPTIONS = [
  { value: "", label: "Ziadne" },
  { value: "monthly", label: "Mesacne" },
  { value: "quarterly", label: "Stvrtrocne" },
  { value: "yearly", label: "Rocne" },
];

function recurrenceLabel(value) {
  return RECURRENCE_OPTIONS.find((item) => item.value === value)?.label || value;
}

function reviewLabel(value) {
  return REVIEW_STATUSES.find((item) => item.value === value)?.label || value || "-";
}

function Field({ label, value }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div className="eyebrow">{label}</div>
      <div className="breakable-text">{value || "-"}</div>
    </div>
  );
}

function LabeledInput({ label, value, onChange }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span className="eyebrow">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle} />
    </label>
  );
}

export default function DocumentDetail({ documentId, onBack }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [events, setEvents] = useState([]);
  const [duplicates, setDuplicates] = useState([]);

  useEffect(() => {
    setDoc(null);
    setError(null);
    Promise.all([
      api.get(`/documents/${documentId}`),
      api.get(`/documents/${documentId}/events`),
      api.get(`/documents/${documentId}/duplicates`),
    ])
      .then(([docRes, eventRes, duplicateRes]) => {
        setDoc(docRes.data);
        setForm(docRes.data);
        setEvents(eventRes.data);
        setDuplicates(duplicateRes.data);
      })
      .catch((err) => setError(err.response?.data?.detail || "Dokument sa nenasiel"));
  }, [documentId]);

  async function refreshSideData() {
    const [eventRes, duplicateRes] = await Promise.all([
      api.get(`/documents/${documentId}/events`),
      api.get(`/documents/${documentId}/duplicates`),
    ]);
    setEvents(eventRes.data);
    setDuplicates(duplicateRes.data);
  }

  async function save() {
    const res = await api.patch(`/documents/${documentId}`, {
      correspondent: form.correspondent,
      doc_type: form.doc_type,
      doc_date: form.doc_date,
      expiry_date: form.expiry_date,
      summary: form.summary,
      review_status: form.review_status,
      notify_recurrence: form.notify_recurrence || null,
    });
    setDoc(res.data);
    setEditing(false);
    refreshSideData();
  }

  async function remove() {
    if (!window.confirm("Naozaj zmazat tento dokument?")) return;
    await api.delete(`/documents/${documentId}`);
    onBack();
  }

  async function dismissExpiry() {
    const res = await api.post(`/documents/${documentId}/expiry-dismissal`);
    setDoc(res.data);
    setForm(res.data);
    refreshSideData();
  }

  async function restoreExpiry() {
    const res = await api.delete(`/documents/${documentId}/expiry-dismissal`);
    setDoc(res.data);
    setForm(res.data);
    refreshSideData();
  }

  async function setReviewStatus(review_status) {
    const res = await api.post(`/documents/${documentId}/review-status`, { review_status });
    setDoc(res.data);
    setForm(res.data);
    refreshSideData();
  }

  async function updateDuplicate(candidateId, status) {
    await api.post(`/documents/duplicates/${candidateId}/status`, { status });
    refreshSideData();
  }

  if (error) return <ErrorState>{error}</ErrorState>;
  if (!doc) return <LoadingBlock />;

  return (
    <div>
      <button className="btn btn-ghost" onClick={onBack} style={{ marginBottom: 16 }}>
        &larr; Spat na hladanie
      </button>
      <PageHeader eyebrow={`Dokument #${doc.id}`} title={doc.correspondent} actions={<StatusBadge status={doc.status} />} />
      <Card>
        {!editing ? (
          <>
            <Field label="Review stav" value={reviewLabel(doc.review_status)} />
            <Field label="Typ" value={doc.doc_type} />
            <Field label="Datum" value={doc.doc_date} />
            {doc.expiry_date && <Field label="Plati do" value={doc.expiry_date} />}
            {doc.expiry_dismissed_at && <Field label="Upozornenie" value={`Vybavene ${doc.expiry_dismissed_at}`} />}
            {doc.notify_recurrence && (
              <Field
                label="Opakovane upozornenie"
                value={`${recurrenceLabel(doc.notify_recurrence)}${doc.next_recurrence_at ? ` (dalsie ${doc.next_recurrence_at})` : ""}`}
              />
            )}
            <Field label="Suma" value={doc.amount_value != null ? `${doc.amount_value} ${doc.amount_currency || ""}` : "-"} />
            <Field label="Zhrnutie" value={doc.summary} />
            <Field label="Zdroj" value={doc.source} />
            <Field label="Povodny nazov" value={doc.original_filename} />
            <Field label="Ulozene v" value={doc.stored_path} />
            {doc.error_message && <Field label="Chyba" value={doc.error_message} />}

            {doc.evidence?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>AI evidence</div>
                <div className="evidence-list">
                  {doc.evidence.map((item, index) => (
                    <div key={`${item.field}-${index}`} className="evidence-row">
                      <strong>{item.field}: {item.value || "-"}</strong>
                      <span>{item.snippet}</span>
                      <small>{Math.round((item.confidence || 0) * 100)}%</small>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {duplicates.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>Mozne duplikaty</div>
                <div className="duplicate-list">
                  {duplicates.map((item) => (
                    <div key={item.id} className="duplicate-row">
                      <div>
                        <strong>#{item.match_id} {item.correspondent}</strong>
                        <span>{item.reason} · {Math.round(item.score * 100)}%</span>
                      </div>
                      <div className="duplicate-actions">
                        <Button variant="secondary" onClick={() => updateDuplicate(item.id, "confirmed")}>
                          Potvrdit
                        </Button>
                        <Button variant="ghost" onClick={() => updateDuplicate(item.id, "ignored")}>
                          Ignorovat
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {doc.status === "processed" && doc.mime_type?.startsWith("image/") && (
              <div style={{ margin: "16px 0" }}>
                <a href={`/api/documents/${doc.id}/file`} target="_blank" rel="noreferrer">
                  <img
                    src={`/api/documents/${doc.id}/file`}
                    alt={doc.original_filename}
                    style={{ maxWidth: "100%", maxHeight: 400, borderRadius: 8, border: "1px solid var(--color-border)" }}
                  />
                </a>
              </div>
            )}

            <div className="detail-actions">
              {doc.status === "processed" && (
                <>
                  <a className="btn btn-secondary" href={`/api/documents/${doc.id}/file`} target="_blank" rel="noreferrer">
                    Zobrazit
                  </a>
                  <a className="btn btn-secondary" href={`/api/documents/${doc.id}/file?download=true`}>
                    Stiahnut
                  </a>
                </>
              )}
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Upravit
              </Button>
              {REVIEW_STATUSES.filter((item) => item.value !== doc.review_status).slice(0, 3).map((item) => (
                <Button key={item.value} variant="secondary" onClick={() => setReviewStatus(item.value)}>
                  {item.label}
                </Button>
              ))}
              {doc.expiry_date && !doc.expiry_dismissed_at && (
                <Button variant="secondary" onClick={dismissExpiry}>
                  Skryt upozornenie
                </Button>
              )}
              {doc.expiry_date && doc.expiry_dismissed_at && (
                <Button variant="secondary" onClick={restoreExpiry}>
                  Obnovit upozornenie
                </Button>
              )}
              <Button variant="ghost" onClick={remove}>
                Zmazat
              </Button>
            </div>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <LabeledInput label="Firma" value={form.correspondent || ""} onChange={(v) => setForm({ ...form, correspondent: v })} />
            <LabeledInput label="Typ" value={form.doc_type || ""} onChange={(v) => setForm({ ...form, doc_type: v })} />
            <LabeledInput label="Datum (YYYY-MM-DD)" value={form.doc_date || ""} onChange={(v) => setForm({ ...form, doc_date: v })} />
            <LabeledInput label="Plati do (YYYY-MM-DD)" value={form.expiry_date || ""} onChange={(v) => setForm({ ...form, expiry_date: v })} />
            <LabeledInput label="Zhrnutie" value={form.summary || ""} onChange={(v) => setForm({ ...form, summary: v })} />
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span className="eyebrow">Review stav</span>
              <select
                value={form.review_status || "na_kontrolu"}
                onChange={(e) => setForm({ ...form, review_status: e.target.value })}
                style={inputStyle}
              >
                {REVIEW_STATUSES.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span className="eyebrow">Opakovane upozornenie (napr. poistka, predplatne)</span>
              <select
                value={form.notify_recurrence || ""}
                onChange={(e) => setForm({ ...form, notify_recurrence: e.target.value })}
                style={inputStyle}
              >
                {RECURRENCE_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <div className="detail-actions">
              <Button onClick={save}>Ulozit</Button>
              <Button variant="ghost" onClick={() => setEditing(false)}>
                Zrusit
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Card style={{ marginTop: 16 }}>
        <h3 style={{ marginBottom: 12 }}>Audit timeline</h3>
        {events.length === 0 && <p style={{ color: "var(--color-text-secondary)" }}>Zatial ziadne udalosti.</p>}
        {events.length > 0 && (
          <div className="timeline-list">
            {events.map((event) => (
              <div key={event.id} className="timeline-row">
                <span>{event.created_at}</span>
                <strong>{event.message}</strong>
                <small>{event.event_type} · {event.actor}</small>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
