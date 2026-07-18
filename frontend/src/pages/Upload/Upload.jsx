import { useState } from "react";
import api from "../../api/client";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";

export default function Upload() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  async function uploadFile(file) {
    setBusy(true);
    setError(null);
    setMessage(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/upload", formData, { timeout: 180000 });
      setMessage(
        res.data.duplicate
          ? `Tento dokument uz mas archivovany (dokument #${res.data.document_id}) - nespracovane znova`
          : `Nahrane a spracovane (dokument #${res.data.document_id})`,
      );
    } catch (err) {
      setError(err.response?.data?.detail || "Nahratie zlyhalo");
    } finally {
      setBusy(false);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Prijem dokumentov"
        title="Nahrat dokument"
        description="Presun sem PDF alebo fotku faktury/zmluvy, alebo ju rovno odfot mobilom."
      />
      <Card onDragOver={(e) => e.preventDefault()} onDrop={handleDrop} style={{ borderStyle: "dashed", textAlign: "center", padding: 48 }}>
        <p style={{ color: "var(--color-text-secondary)" }}>Presun sem subor, alebo</p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 16, flexWrap: "wrap" }}>
          <label className="btn btn-secondary">
            Vybrat subor
            <input
              type="file"
              hidden
              onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
            />
          </label>
          <label className="btn btn-primary">
            Odfotit (mobil)
            <input
              type="file"
              accept="image/*"
              capture="environment"
              hidden
              onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
            />
          </label>
        </div>
        {busy && <p style={{ marginTop: 16, color: "var(--color-text-secondary)" }}>Spracovavam...</p>}
        {message && <p style={{ marginTop: 16, color: "var(--color-success)" }}>{message}</p>}
        {error && <p style={{ marginTop: 16, color: "var(--color-warning)" }}>{error}</p>}
      </Card>
    </div>
  );
}
