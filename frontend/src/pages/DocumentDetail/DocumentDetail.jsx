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

function Field({ label, value }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div className="eyebrow">{label}</div>
      <div>{value || "-"}</div>
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

  useEffect(() => {
    setDoc(null);
    setError(null);
    api
      .get(`/documents/${documentId}`)
      .then((res) => {
        setDoc(res.data);
        setForm(res.data);
      })
      .catch((err) => setError(err.response?.data?.detail || "Dokument sa nenasiel"));
  }, [documentId]);

  async function save() {
    const res = await api.patch(`/documents/${documentId}`, {
      correspondent: form.correspondent,
      doc_type: form.doc_type,
      doc_date: form.doc_date,
      summary: form.summary,
    });
    setDoc(res.data);
    setEditing(false);
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
            <Field label="Typ" value={doc.doc_type} />
            <Field label="Datum" value={doc.doc_date} />
            <Field label="Suma" value={doc.amount_value != null ? `${doc.amount_value} ${doc.amount_currency || ""}` : "-"} />
            <Field label="Zhrnutie" value={doc.summary} />
            <Field label="Zdroj" value={doc.source} />
            <Field label="Povodny nazov" value={doc.original_filename} />
            <Field label="Ulozene v" value={doc.stored_path} />
            {doc.error_message && <Field label="Chyba" value={doc.error_message} />}
            <Button variant="secondary" onClick={() => setEditing(true)} style={{ marginTop: 8 }}>
              Upravit
            </Button>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <LabeledInput label="Firma" value={form.correspondent || ""} onChange={(v) => setForm({ ...form, correspondent: v })} />
            <LabeledInput label="Typ" value={form.doc_type || ""} onChange={(v) => setForm({ ...form, doc_type: v })} />
            <LabeledInput label="Datum (YYYY-MM-DD)" value={form.doc_date || ""} onChange={(v) => setForm({ ...form, doc_date: v })} />
            <LabeledInput label="Zhrnutie" value={form.summary || ""} onChange={(v) => setForm({ ...form, summary: v })} />
            <div style={{ display: "flex", gap: 8 }}>
              <Button onClick={save}>Ulozit</Button>
              <Button variant="ghost" onClick={() => setEditing(false)}>
                Zrusit
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
