import { useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import { useI18n } from "../../i18n.jsx";

export default function Upload() {
  const { apiErrorMessage, documentUnit, fileUnit, pageUnit, t } = useI18n();
  const [staged, setStaged] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  function addFiles(fileList) {
    const files = Array.from(fileList || []);
    if (files.length) setStaged((prev) => [...prev, ...files]);
  }

  function removeStaged(index) {
    setStaged((prev) => prev.filter((_, i) => i !== index));
  }

  function moveStaged(index, direction) {
    setStaged((prev) => {
      const next = [...prev];
      const target = index + direction;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function describeResult(data, combinedCount) {
    if (data.duplicate) {
      return t("upload.duplicate", { id: data.document_id });
    }
    return combinedCount
      ? t("upload.combined", { count: combinedCount, unit: pageUnit(combinedCount), id: data.document_id })
      : t("upload.processed", { id: data.document_id });
  }

  async function uploadSingle(file) {
    setBusy(true);
    setError(null);
    setMessage(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/upload", formData, { timeout: 180000 });
      setMessage(describeResult(res.data));
      setStaged([]);
    } catch (err) {
      setError(apiErrorMessage(err, t("upload.failed")));
    } finally {
      setBusy(false);
    }
  }

  async function uploadCombined() {
    setBusy(true);
    setError(null);
    setMessage(null);
    const formData = new FormData();
    staged.forEach((file) => formData.append("files", file));
    try {
      const res = await api.post("/upload/combine", formData, { timeout: 180000 });
      setMessage(describeResult(res.data, staged.length));
      setStaged([]);
    } catch (err) {
      setError(apiErrorMessage(err, t("upload.combineFailed")));
    } finally {
      setBusy(false);
    }
  }

  async function uploadEachSeparately() {
    setBusy(true);
    setError(null);
    setMessage(null);
    let uploaded = 0;
    try {
      for (const file of staged) {
        const formData = new FormData();
        formData.append("file", file);
        await api.post("/upload", formData, { timeout: 180000 });
        uploaded += 1;
      }
      setMessage(t("upload.uploadedSeparate", { count: uploaded, unit: documentUnit(uploaded) }));
      setStaged([]);
    } catch (err) {
      setError(apiErrorMessage(err, t("upload.failedAfter", { count: uploaded, unit: fileUnit(uploaded) })));
    } finally {
      setBusy(false);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    addFiles(e.dataTransfer.files);
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("upload.eyebrow")}
        title={t("upload.title")}
        description={t("upload.description")}
      />
      <Card onDragOver={(e) => e.preventDefault()} onDrop={handleDrop} style={{ borderStyle: "dashed", textAlign: "center", padding: 48 }}>
        <p style={{ color: "var(--color-text-secondary)" }}>{t("upload.drop")}</p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 16, flexWrap: "wrap" }}>
          <label className="btn btn-secondary">
            {t("upload.chooseFiles")}
            <input type="file" multiple hidden onChange={(e) => addFiles(e.target.files)} />
          </label>
          <label className="btn btn-primary">
            {t("upload.takePhoto")}
            <input type="file" accept="image/*" capture="environment" hidden onChange={(e) => addFiles(e.target.files)} />
          </label>
        </div>

        {staged.length > 0 && (
          <div style={{ marginTop: 24, textAlign: "left" }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              {t("upload.ready", { count: staged.length })}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
              {staged.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "6px 10px",
                    background: "var(--color-ink-secondary)",
                    borderRadius: 8,
                  }}
                >
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-text-secondary)" }}>
                    {index + 1}.
                  </span>
                  <span style={{ flex: 1, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {file.name}
                  </span>
                  <button className="btn btn-ghost" onClick={() => moveStaged(index, -1)} disabled={index === 0}>
                    {t("upload.up")}
                  </button>
                  <button className="btn btn-ghost" onClick={() => moveStaged(index, 1)} disabled={index === staged.length - 1}>
                    {t("upload.down")}
                  </button>
                  <button className="btn btn-ghost" onClick={() => removeStaged(index)}>
                    {t("common.remove")}
                  </button>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
              {staged.length === 1 ? (
                <Button onClick={() => uploadSingle(staged[0])} disabled={busy}>
                  {t("upload.upload")}
                </Button>
              ) : (
                <>
                  <Button onClick={uploadCombined} disabled={busy}>
                    {t("upload.combine", { count: staged.length, unit: pageUnit(staged.length) })}
                  </Button>
                  <Button variant="secondary" onClick={uploadEachSeparately} disabled={busy}>
                    {t("upload.eachSeparately")}
                  </Button>
                </>
              )}
              <Button variant="ghost" onClick={() => setStaged([])} disabled={busy}>
                {t("common.cancel")}
              </Button>
            </div>
          </div>
        )}

        {busy && <p style={{ marginTop: 16, color: "var(--color-text-secondary)" }}>{t("upload.processing")}</p>}
        {message && <p style={{ marginTop: 16, color: "var(--color-success)" }}>{message}</p>}
        {error && <p style={{ marginTop: 16, color: "var(--color-warning)" }}>{error}</p>}
      </Card>
    </div>
  );
}
