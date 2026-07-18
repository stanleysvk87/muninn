import { useEffect, useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import { useI18n } from "../../i18n.jsx";

const inputStyle = {
  padding: "10px 12px",
  borderRadius: 8,
  border: "1px solid var(--color-border-strong)",
  background: "var(--color-ink-secondary)",
  color: "var(--color-text-primary)",
  width: "100%",
};

export default function Settings() {
  const { apiErrorMessage, t } = useI18n();
  const [folders, setFolders] = useState([]);
  const [newFolder, setNewFolder] = useState("");
  const [folderError, setFolderError] = useState(null);
  const [mail, setMail] = useState({});
  const [aiMode, setAiMode] = useState("auto");
  const [apiKey, setApiKey] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [usage, setUsage] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [telegram, setTelegram] = useState({});
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [telegramTestResult, setTelegramTestResult] = useState(null);

  useEffect(() => {
    Promise.all([
      api.get("/settings/watch-folders"),
      api.get("/settings/mail"),
      api.get("/settings/ai-provider"),
      api.get("/settings/usage"),
      api.get("/settings/diagnostics"),
      api.get("/settings/telegram"),
    ]).then(([f, m, a, u, d, t]) => {
      setFolders(f.data.folders);
      setMail(m.data);
      setAiMode(a.data.mode);
      setUsage(u.data);
      setDiagnostics(d.data);
      setTelegram(t.data);
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
      setFolderError(apiErrorMessage(err));
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
      setTestResult(t("settings.testError", { detail: apiErrorMessage(err, t("common.unknown")) }));
    }
  }

  async function saveTelegram() {
    const res = await api.put("/settings/telegram", {
      enabled: telegram.enabled,
      chat_id: telegram.chat_id,
      notify_days_before: telegram.notify_days_before,
      notification_language: telegram.notification_language,
      bot_token: telegramBotToken || undefined,
    });
    setTelegram(res.data);
    setTelegramBotToken("");
  }

  async function testTelegram() {
    setTelegramTestResult(null);
    try {
      const res = await api.post("/settings/telegram/test");
      setTelegramTestResult(`OK: ${res.data.message}`);
    } catch (err) {
      setTelegramTestResult(t("settings.testError", { detail: apiErrorMessage(err, t("common.unknown")) }));
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <PageHeader eyebrow={t("settings.eyebrow")} title={t("settings.title")} />

      <Card>
        <h3 style={{ marginBottom: 12 }}>{t("settings.watchFolders")}</h3>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, marginBottom: 12 }}>
          {folders.map((f) => (
            <li key={f} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{f}</span>
              <button className="btn btn-ghost" onClick={() => removeFolder(f)}>
                {t("common.remove")}
              </button>
            </li>
          ))}
          {folders.length === 0 && <li style={{ color: "var(--color-text-secondary)" }}>{t("settings.noFolders")}</li>}
        </ul>
        <div style={{ display: "flex", gap: 8 }}>
          <input value={newFolder} onChange={(e) => setNewFolder(e.target.value)} placeholder={t("settings.folderPlaceholder")} style={inputStyle} />
          <Button onClick={addFolder}>{t("settings.add")}</Button>
        </div>
        {folderError && <p style={{ color: "var(--color-warning)", marginTop: 8 }}>{folderError}</p>}
      </Card>

      <Card>
        <h3 style={{ marginBottom: 12 }}>{t("settings.mail")}</h3>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <input type="checkbox" checked={!!mail.enabled} onChange={(e) => setMail({ ...mail, enabled: e.target.checked })} />
          {t("settings.enableMail")}
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <input placeholder={t("settings.imapHost")} value={mail.host || ""} onChange={(e) => setMail({ ...mail, host: e.target.value })} style={inputStyle} />
          <input
            placeholder={t("settings.port")}
            type="number"
            value={mail.port || 993}
            onChange={(e) => setMail({ ...mail, port: Number(e.target.value) })}
            style={inputStyle}
          />
          <input
            placeholder={t("settings.username")}
            value={mail.username || ""}
            onChange={(e) => setMail({ ...mail, username: e.target.value })}
            style={inputStyle}
          />
          <input placeholder={t("settings.password")} type="password" onChange={(e) => setMail({ ...mail, password: e.target.value })} style={inputStyle} />
        </div>
        <Button onClick={saveMail} style={{ marginTop: 12 }}>
          {t("common.save")}
        </Button>
      </Card>

      <Card>
        <h3 style={{ marginBottom: 12 }}>{t("settings.telegram")}</h3>
        <p style={{ color: "var(--color-text-secondary)", fontSize: 13, marginBottom: 12 }}>
          {t("settings.telegramDescription")}
        </p>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <input
            type="checkbox"
            checked={!!telegram.enabled}
            onChange={(e) => setTelegram({ ...telegram, enabled: e.target.checked })}
          />
          {t("settings.enableTelegram")}
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <input
            placeholder={t("settings.botToken")}
            type="password"
            value={telegramBotToken}
            onChange={(e) => setTelegramBotToken(e.target.value)}
            style={inputStyle}
          />
          <input
            placeholder={t("settings.chatId")}
            value={telegram.chat_id || ""}
            onChange={(e) => setTelegram({ ...telegram, chat_id: e.target.value })}
            style={inputStyle}
          />
          <input
            placeholder={t("settings.notifyDays")}
            type="number"
            value={telegram.notify_days_before ?? 30}
            onChange={(e) => setTelegram({ ...telegram, notify_days_before: Number(e.target.value) })}
            style={inputStyle}
          />
          <select
            value={telegram.notification_language || "sk"}
            onChange={(e) => setTelegram({ ...telegram, notification_language: e.target.value })}
            style={inputStyle}
          >
            <option value="sk">{t("settings.notificationLanguageSk")}</option>
            <option value="en">{t("settings.notificationLanguageEn")}</option>
          </select>
        </div>
        {telegram.configured && (
          <p style={{ marginTop: 8, fontSize: 12, color: "var(--color-text-secondary)" }}>
            {t("settings.tokenStored")}
          </p>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <Button onClick={saveTelegram}>{t("common.save")}</Button>
          <Button variant="secondary" onClick={testTelegram}>
            {t("settings.test")}
          </Button>
        </div>
        {telegramTestResult && <p style={{ marginTop: 8 }}>{telegramTestResult}</p>}
      </Card>

      <Card>
        <h3 style={{ marginBottom: 12 }}>{t("settings.aiEngine")}</h3>
        <select value={aiMode} onChange={(e) => setAiMode(e.target.value)} style={inputStyle}>
          <option value="auto">{t("settings.modeAuto")}</option>
          <option value="claude_cli">{t("settings.modeClaude")}</option>
          <option value="codex_cli">{t("settings.modeCodex")}</option>
          <option value="anthropic_api">{t("settings.modeAnthropic")}</option>
        </select>
        <input
          placeholder={t("settings.apiKey")}
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          style={{ ...inputStyle, marginTop: 12 }}
        />
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <Button onClick={saveAiProvider}>{t("common.save")}</Button>
          <Button variant="secondary" onClick={testConnection}>
            {t("settings.testConnection")}
          </Button>
        </div>
        {testResult && <p style={{ marginTop: 8 }}>{testResult}</p>}
      </Card>

      <Card>
        <h3 style={{ marginBottom: 12 }}>{t("settings.aiUsage")}</h3>
        {!usage ? (
          <p style={{ color: "var(--color-text-secondary)" }}>{t("common.loading")}</p>
        ) : usage.total.documents === 0 ? (
          <p style={{ color: "var(--color-text-secondary)" }}>{t("settings.noProcessed")}</p>
        ) : (
          <>
            <div className="settings-metrics">
              <div>
                <div className="eyebrow">{t("settings.processedDocuments")}</div>
                <div style={{ fontSize: 20 }}>{usage.total.documents}</div>
              </div>
              <div>
                <div className="eyebrow">{t("settings.tokenCosts")}</div>
                <div style={{ fontSize: 20 }}>${usage.total.cost_usd.toFixed(4)}</div>
              </div>
              <div>
                <div className="eyebrow">{t("settings.measuredTokens")}</div>
                <div style={{ fontSize: 20 }}>
                  {usage.total.input_tokens.toLocaleString()} / {usage.total.output_tokens.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="eyebrow">{t("settings.cliCalls")}</div>
                <div style={{ fontSize: 20 }}>{usage.metering?.cli_documents ?? 0}</div>
              </div>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--color-text-secondary)" }}>
                  <th style={{ padding: "4px 8px" }}>{t("settings.provider")}</th>
                  <th style={{ padding: "4px 8px" }}>{t("settings.documents")}</th>
                  <th style={{ padding: "4px 8px" }}>{t("settings.costs")}</th>
                  <th style={{ padding: "4px 8px" }}>{t("settings.tokens")}</th>
                </tr>
              </thead>
              <tbody>
                {usage.by_provider.map((row) => (
                  <tr key={row.ai_provider || "unknown"}>
                    <td style={{ padding: "4px 8px" }}>{row.ai_provider || t("common.unknown")}</td>
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
              {t("settings.usageNote")}
            </p>
          </>
        )}
      </Card>

      <Card>
        <h3 style={{ marginBottom: 12 }}>{t("settings.technicalStatus")}</h3>
        {!diagnostics ? (
          <p style={{ color: "var(--color-text-secondary)" }}>{t("common.loading")}</p>
        ) : (
          <>
            <div className="settings-metrics">
              <div>
                <div className="eyebrow">{t("settings.aiMode")}</div>
                <div>{diagnostics.ai_mode}</div>
              </div>
              <div>
                <div className="eyebrow">Claude CLI</div>
                <div style={{ color: diagnostics.cli.claude.available ? "var(--color-success)" : "var(--color-warning)" }}>
                  {diagnostics.cli.claude.available ? t("settings.available") : t("settings.missing")}
                </div>
              </div>
              <div>
                <div className="eyebrow">Codex CLI</div>
                <div style={{ color: diagnostics.cli.codex.available ? "var(--color-success)" : "var(--color-warning)" }}>
                  {diagnostics.cli.codex.available ? t("settings.available") : t("settings.missing")}
                </div>
              </div>
              <div>
                <div className="eyebrow">{t("settings.mailUidFailed")}</div>
                <div>{diagnostics.mail.last_uid} / {diagnostics.mail.failed_uid_count}</div>
              </div>
            </div>
            <div style={{ marginTop: 12, color: "var(--color-text-secondary)", fontSize: 13 }}>
              {t("settings.providerChain")}: {diagnostics.provider_chain.map((p) => p.name).join(" -> ") || "-"}
            </div>
            {diagnostics.documents.recent_failed.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>{t("settings.recentErrors")}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {diagnostics.documents.recent_failed.map((row) => (
                    <div key={row.id} className="diagnostic-row">
                      <strong>#{row.id} {row.original_filename}</strong>
                      <span>{row.ai_provider || t("common.providerUnknown")}: {row.error_message || t("common.noDetail")}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {diagnostics.documents.recent_failed.length === 0 && (
              <p style={{ marginTop: 12, color: "var(--color-text-secondary)" }}>{t("settings.noFailed")}</p>
            )}
            {diagnostics.jobs?.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="eyebrow" style={{ marginBottom: 8 }}>{t("settings.recentJobs")}</div>
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
                          {t("common.retry")}
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <Button variant="secondary" onClick={refreshDiagnostics} style={{ marginTop: 12 }}>
              {t("settings.refreshStatus")}
            </Button>
          </>
        )}
      </Card>

      <p style={{ fontSize: 12, color: "var(--color-text-secondary)", textAlign: "center" }}>
        <a href="/ochrana-udajov.html" target="_blank" rel="noreferrer">
          {t("settings.privacyLink")}
        </a>
      </p>
    </div>
  );
}
