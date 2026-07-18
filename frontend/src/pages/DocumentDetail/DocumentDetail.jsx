import { useEffect, useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import ErrorState from "../../components/ui/ErrorState";
import LoadingBlock from "../../components/ui/LoadingBlock";
import PageHeader from "../../components/ui/PageHeader";
import StatusBadge from "../../components/ui/StatusBadge";
import { useI18n } from "../../i18n.jsx";

const inputStyle = {
  padding: "8px 12px",
  borderRadius: 8,
  border: "1px solid var(--color-border-strong)",
  background: "var(--color-ink-secondary)",
  color: "var(--color-text-primary)",
};

const REVIEW_STATUSES = ["na_kontrolu", "zaplatit", "vybavene", "zamietnute", "archiv"];

const RECURRENCE_OPTIONS = [
  "",
  "monthly",
  "quarterly",
  "yearly",
];

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
  const { apiErrorMessage, docTypeLabel, duplicateReason, eventMessage, localizedSummary, recurrenceLabel, reviewLabel, t } = useI18n();
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
      .catch((err) => setError(apiErrorMessage(err, t("detail.notFound"))));
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
    if (!window.confirm(t("detail.deleteConfirm"))) return;
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
        &larr; {t("detail.back")}
      </button>
      <PageHeader eyebrow={`Dokument #${doc.id}`} title={doc.correspondent} actions={<StatusBadge status={doc.status} />} />
      <Card>
        {!editing ? (
          <>
            <Field label={t("detail.reviewStatus")} value={reviewLabel(doc.review_status)} />
            <Field label={t("detail.type")} value={docTypeLabel(doc.doc_type)} />
            <Field label={t("detail.date")} value={doc.doc_date} />
            {doc.expiry_date && <Field label={t("detail.validUntil")} value={doc.expiry_date} />}
            {doc.expiry_dismissed_at && <Field label={t("detail.alert")} value={t("detail.doneAt", { date: doc.expiry_dismissed_at })} />}
            {doc.notify_recurrence && (
              <Field
                label={t("detail.recurrence")}
                value={`${recurrenceLabel(doc.notify_recurrence)}${doc.next_recurrence_at ? ` (${t("detail.next", { date: doc.next_recurrence_at })})` : ""}`}
              />
            )}
            <Field label={t("detail.amount")} value={doc.amount_value != null ? `${doc.amount_value} ${doc.amount_currency || ""}` : "-"} />
            <Field label={t("detail.summary")} value={localizedSummary(doc)} />
            <Field label={t("detail.source")} value={doc.source} />
            <Field label={t("detail.originalName")} value={doc.original_filename} />
            <Field label={t("detail.storedIn")} value={doc.stored_path} />
            {doc.error_message && <Field label={t("common.error")} value={doc.error_message} />}

            {doc.evidence?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>{t("detail.aiEvidence")}</div>
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
                <div className="eyebrow" style={{ marginBottom: 8 }}>{t("detail.possibleDuplicates")}</div>
                <div className="duplicate-list">
                  {duplicates.map((item) => (
                    <div key={item.id} className="duplicate-row">
                      <div>
                        <strong>#{item.match_id} {item.correspondent}</strong>
                        <span>{duplicateReason(item.reason)} · {Math.round(item.score * 100)}%</span>
                      </div>
                      <div className="duplicate-actions">
                        <Button variant="secondary" onClick={() => updateDuplicate(item.id, "confirmed")}>
                          {t("detail.confirmDuplicate")}
                        </Button>
                        <Button variant="ghost" onClick={() => updateDuplicate(item.id, "ignored")}>
                          {t("detail.ignoreDuplicate")}
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
                    {t("common.view")}
                  </a>
                  <a className="btn btn-secondary" href={`/api/documents/${doc.id}/file?download=true`}>
                    {t("common.download")}
                  </a>
                </>
              )}
              <Button variant="secondary" onClick={() => setEditing(true)}>
                {t("common.edit")}
              </Button>
              {REVIEW_STATUSES.filter((value) => value !== doc.review_status).slice(0, 3).map((value) => (
                <Button key={value} variant="secondary" onClick={() => setReviewStatus(value)}>
                  {reviewLabel(value)}
                </Button>
              ))}
              {doc.expiry_date && !doc.expiry_dismissed_at && (
                <Button variant="secondary" onClick={dismissExpiry}>
                  {t("detail.hideAlert")}
                </Button>
              )}
              {doc.expiry_date && doc.expiry_dismissed_at && (
                <Button variant="secondary" onClick={restoreExpiry}>
                  {t("detail.restoreAlert")}
                </Button>
              )}
              <Button variant="ghost" onClick={remove}>
                {t("common.delete")}
              </Button>
            </div>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <LabeledInput label={t("detail.company")} value={form.correspondent || ""} onChange={(v) => setForm({ ...form, correspondent: v })} />
            <LabeledInput label={t("detail.type")} value={form.doc_type || ""} onChange={(v) => setForm({ ...form, doc_type: v })} />
            <LabeledInput label={t("detail.dateInput")} value={form.doc_date || ""} onChange={(v) => setForm({ ...form, doc_date: v })} />
            <LabeledInput label={t("detail.validUntilInput")} value={form.expiry_date || ""} onChange={(v) => setForm({ ...form, expiry_date: v })} />
            <LabeledInput label={t("detail.summary")} value={form.summary || ""} onChange={(v) => setForm({ ...form, summary: v })} />
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span className="eyebrow">{t("detail.reviewStatus")}</span>
              <select
                value={form.review_status || "na_kontrolu"}
                onChange={(e) => setForm({ ...form, review_status: e.target.value })}
                style={inputStyle}
              >
                {REVIEW_STATUSES.map((value) => (
                  <option key={value} value={value}>{reviewLabel(value)}</option>
                ))}
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span className="eyebrow">{t("detail.recurrenceInput")}</span>
              <select
                value={form.notify_recurrence || ""}
                onChange={(e) => setForm({ ...form, notify_recurrence: e.target.value })}
                style={inputStyle}
              >
                {RECURRENCE_OPTIONS.map((value) => (
                  <option key={value || "none"} value={value}>{recurrenceLabel(value)}</option>
                ))}
              </select>
            </label>
            <div className="detail-actions">
              <Button onClick={save}>{t("common.save")}</Button>
              <Button variant="ghost" onClick={() => setEditing(false)}>
                {t("common.cancel")}
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Card style={{ marginTop: 16 }}>
        <h3 style={{ marginBottom: 12 }}>{t("detail.auditTimeline")}</h3>
        {events.length === 0 && <p style={{ color: "var(--color-text-secondary)" }}>{t("detail.noEvents")}</p>}
        {events.length > 0 && (
          <div className="timeline-list">
            {events.map((event) => (
              <div key={event.id} className="timeline-row">
                <span>{event.created_at}</span>
                <strong>{eventMessage(event)}</strong>
                <small>{event.event_type} · {event.actor}</small>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
