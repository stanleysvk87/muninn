import { useEffect, useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";

const inputStyle = {
  padding: "10px 12px",
  borderRadius: 8,
  border: "1px solid var(--color-border-strong)",
  background: "var(--color-ink-secondary)",
  color: "var(--color-text-primary)",
  width: "100%",
};

export default function Settings() {
  const [folders, setFolders] = useState([]);
  const [newFolder, setNewFolder] = useState("");
  const [folderError, setFolderError] = useState(null);
  const [mail, setMail] = useState({});
  const [aiMode, setAiMode] = useState("auto");
  const [apiKey, setApiKey] = useState("");
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    Promise.all([
      api.get("/settings/watch-folders"),
      api.get("/settings/mail"),
      api.get("/settings/ai-provider"),
    ]).then(([f, m, a]) => {
      setFolders(f.data.folders);
      setMail(m.data);
      setAiMode(a.data.mode);
    });
  }, []);

  async function addFolder() {
    setFolderError(null);
    try {
      const res = await api.post("/settings/watch-folders", { path: newFolder });
      setFolders(res.data.folders);
      setNewFolder("");
    } catch (err) {
      setFolderError(err.response?.data?.detail);
    }
  }

  async function removeFolder(path) {
    const res = await api.delete("/settings/watch-folders", { params: { path } });
    setFolders(res.data.folders);
  }

  async function saveMail() {
    await api.put("/settings/mail", mail);
  }

  async function saveAiProvider() {
    await api.put("/settings/ai-provider", { mode: aiMode, api_key: apiKey || undefined });
    setApiKey("");
  }

  async function testConnection() {
    setTestResult(null);
    try {
      const res = await api.post("/settings/ai-provider/test");
      setTestResult(`OK: ${res.data.provider} (${res.data.model})`);
    } catch (err) {
      setTestResult(`Chyba: ${err.response?.data?.detail}`);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <PageHeader eyebrow="Konfiguracia" title="Nastavenia" />

      <Card>
        <h3 style={{ marginBottom: 12 }}>Sledovane priecinky</h3>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, marginBottom: 12 }}>
          {folders.map((f) => (
            <li key={f} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{f}</span>
              <button className="btn btn-ghost" onClick={() => removeFolder(f)}>
                Odstranit
              </button>
            </li>
          ))}
          {folders.length === 0 && <li style={{ color: "var(--color-text-secondary)" }}>Ziadne priecinky</li>}
        </ul>
        <div style={{ display: "flex", gap: 8 }}>
          <input value={newFolder} onChange={(e) => setNewFolder(e.target.value)} placeholder="/cesta/k/priecinku" style={inputStyle} />
          <Button onClick={addFolder}>Pridat</Button>
        </div>
        {folderError && <p style={{ color: "var(--color-warning)", marginTop: 8 }}>{folderError}</p>}
      </Card>

      <Card>
        <h3 style={{ marginBottom: 12 }}>Mail (volitelne)</h3>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <input type="checkbox" checked={!!mail.enabled} onChange={(e) => setMail({ ...mail, enabled: e.target.checked })} />
          Zapnut mail ingestion
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <input placeholder="IMAP host" value={mail.host || ""} onChange={(e) => setMail({ ...mail, host: e.target.value })} style={inputStyle} />
          <input
            placeholder="Port"
            type="number"
            value={mail.port || 993}
            onChange={(e) => setMail({ ...mail, port: Number(e.target.value) })}
            style={inputStyle}
          />
          <input
            placeholder="Pouzivatelske meno"
            value={mail.username || ""}
            onChange={(e) => setMail({ ...mail, username: e.target.value })}
            style={inputStyle}
          />
          <input placeholder="Heslo" type="password" onChange={(e) => setMail({ ...mail, password: e.target.value })} style={inputStyle} />
        </div>
        <Button onClick={saveMail} style={{ marginTop: 12 }}>
          Ulozit
        </Button>
      </Card>

      <Card>
        <h3 style={{ marginBottom: 12 }}>AI engine</h3>
        <select value={aiMode} onChange={(e) => setAiMode(e.target.value)} style={inputStyle}>
          <option value="auto">Automaticky (claude/codex CLI, potom API kluc)</option>
          <option value="claude_cli">Len Claude CLI</option>
          <option value="codex_cli">Len Codex CLI</option>
          <option value="anthropic_api">Len Anthropic API kluc</option>
        </select>
        <input
          placeholder="Anthropic API kluc (ak treba)"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          style={{ ...inputStyle, marginTop: 12 }}
        />
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <Button onClick={saveAiProvider}>Ulozit</Button>
          <Button variant="secondary" onClick={testConnection}>
            Otestovat pripojenie
          </Button>
        </div>
        {testResult && <p style={{ marginTop: 8 }}>{testResult}</p>}
      </Card>
    </div>
  );
}
