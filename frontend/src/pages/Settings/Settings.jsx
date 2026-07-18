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
  const [usage, setUsage] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);

  useEffect(() => {
    Promise.all([
      api.get("/settings/watch-folders"),
      api.get("/settings/mail"),
      api.get("/settings/ai-provider"),
      api.get("/settings/usage"),
      api.get("/settings/diagnostics"),
    ]).then(([f, m, a, u, d]) => {
      setFolders(f.data.folders);
      setMail(m.data);
      setAiMode(a.data.mode);
      setUsage(u.data);
      setDiagnostics(d.data);
    });
  }, []);

  async function refreshDiagnostics() {
    const [u, d] = await Promise.all([
      api.get("/settings/usage"),
      api.get("/settings/diagnostics"),
    ]);
    setUsage(u.data);
    setDiagnostics(d.data);
  }

  async function retryFailedDocument(documentId) {
    await api.post(`/documents/${documentId}/retry`);
    refreshDiagnostics();
  }

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

      <Card>
        <h3 style={{ marginBottom: 12 }}>Spotreba AI</h3>
        {!usage ? (
          <p style={{ color: "var(--color-text-secondary)" }}>Nacitavam...</p>
        ) : usage.total.documents === 0 ? (
          <p style={{ color: "var(--color-text-secondary)" }}>Zatial ziadne spracovane dokumenty</p>
        ) : (
          <>
            <div className="settings-metrics">
              <div>
                <div className="eyebrow">Spracovanych dokumentov</div>
                <div style={{ fontSize: 20 }}>{usage.total.documents}</div>
              </div>
              <div>
                <div className="eyebrow">API/Claude token naklady</div>
                <div style={{ fontSize: 20 }}>${usage.total.cost_usd.toFixed(4)}</div>
              </div>
              <div>
                <div className="eyebrow">Merane tokeny in/out</div>
                <div style={{ fontSize: 20 }}>
                  {usage.total.input_tokens.toLocaleString()} / {usage.total.output_tokens.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="eyebrow">CLI volania</div>
                <div style={{ fontSize: 20 }}>{usage.metering?.cli_documents ?? 0}</div>
              </div>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--color-text-secondary)" }}>
                  <th style={{ padding: "4px 8px" }}>Provider</th>
                  <th style={{ padding: "4px 8px" }}>Dokumentov</th>
                  <th style={{ padding: "4px 8px" }}>Naklady</th>
                  <th style={{ padding: "4px 8px" }}>Tokeny in/out</th>
                </tr>
              </thead>
              <tbody>
                {usage.by_provider.map((row) => (
                  <tr key={row.ai_provider || "neznamy"}>
                    <td style={{ padding: "4px 8px" }}>{row.ai_provider || "neznamy"}</td>
                    <td style={{ padding: "4px 8px" }}>{row.documents}</td>
                    <td style={{ padding: "4px 8px" }}>${row.cost_usd.toFixed(4)}</td>
                    <td style={{ padding: "4px 8px" }}>
                      {row.input_tokens.toLocaleString()} / {row.output_tokens.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p style={{ marginTop: 12, fontSize: 12, color: "var(--color-text-secondary)" }}>
              {usage.metering?.note}
            </p>
          </>
        )}
      </Card>

      <Card>
        <h3 style={{ marginBottom: 12 }}>Technicky stav</h3>
        {!diagnostics ? (
          <p style={{ color: "var(--color-text-secondary)" }}>Nacitavam...</p>
        ) : (
          <>
            <div className="settings-metrics">
              <div>
                <div className="eyebrow">AI rezim</div>
                <div>{diagnostics.ai_mode}</div>
              </div>
              <div>
                <div className="eyebrow">Claude CLI</div>
                <div style={{ color: diagnostics.cli.claude.available ? "var(--color-success)" : "var(--color-warning)" }}>
                  {diagnostics.cli.claude.available ? "dostupny" : "chyba"}
                </div>
              </div>
              <div>
                <div className="eyebrow">Codex CLI</div>
                <div style={{ color: diagnostics.cli.codex.available ? "var(--color-success)" : "var(--color-warning)" }}>
                  {diagnostics.cli.codex.available ? "dostupny" : "chyba"}
                </div>
              </div>
              <div>
                <div className="eyebrow">Mail UID / failed</div>
                <div>{diagnostics.mail.last_uid} / {diagnostics.mail.failed_uid_count}</div>
              </div>
            </div>
            <div style={{ marginTop: 12, color: "var(--color-text-secondary)", fontSize: 13 }}>
              Provider chain: {diagnostics.provider_chain.map((p) => p.name).join(" -> ") || "-"}
            </div>
            {diagnostics.documents.recent_failed.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>Posledne chyby</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {diagnostics.documents.recent_failed.map((row) => (
                    <div key={row.id} className="diagnostic-row">
                      <strong>#{row.id} {row.original_filename}</strong>
                      <span>{row.ai_provider || "provider?"}: {row.error_message || "bez detailu"}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {diagnostics.documents.recent_failed.length === 0 && (
              <p style={{ marginTop: 12, color: "var(--color-text-secondary)" }}>Ziadne failed dokumenty v aktivnej DB.</p>
            )}
            {diagnostics.jobs?.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>Posledne joby</div>
                <div className="job-log-list">
                  {diagnostics.jobs.map((job) => (
                    <div key={job.id} className="job-log-row">
                      <div>
                        <strong>#{job.id} {job.original_filename}</strong>
                        <span>
                          {job.status} · {job.source}{job.ai_provider ? ` · ${job.ai_provider}` : ""}
                        </span>
                        {job.error_message && <small>{job.error_message}</small>}
                      </div>
                      {job.status === "failed" && job.document_id && (
                        <Button variant="secondary" onClick={() => retryFailedDocument(job.document_id)}>
                          Retry
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <Button variant="secondary" onClick={refreshDiagnostics} style={{ marginTop: 12 }}>
              Obnovit stav
            </Button>
          </>
        )}
      </Card>
    </div>
  );
}
