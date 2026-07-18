import { useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { useI18n } from "../../i18n.jsx";

const inputStyle = {
  padding: "10px 12px",
  borderRadius: 8,
  border: "1px solid var(--color-border-strong)",
  background: "var(--color-ink-secondary)",
  color: "var(--color-text-primary)",
};

export default function Login({ onLoggedIn }) {
  const { apiErrorMessage, language, setLanguage, t } = useI18n();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/bootstrap";
      const payload = mode === "login" ? { username, password } : { username, password, consent };
      const res = await api.post(path, payload);
      onLoggedIn(res.data);
    } catch (err) {
      setError(apiErrorMessage(err, t("login.failed")));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Card style={{ width: 360 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <div className="eyebrow">Muninn</div>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            aria-label={t("common.language")}
            style={{ ...inputStyle, width: "auto", padding: "6px 8px", fontSize: 12 }}
          >
            <option value="sk">SK</option>
            <option value="en">EN</option>
          </select>
        </div>
        <h1 style={{ fontSize: 22, marginTop: 8, marginBottom: 20 }}>
          {mode === "login" ? t("login.title") : t("login.bootstrapTitle")}
        </h1>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <input
            placeholder={t("login.username")}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            style={inputStyle}
          />
          <input
            type="password"
            placeholder={t("login.password")}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={inputStyle}
          />
          {mode === "bootstrap" && (
            <label style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 12, color: "var(--color-text-secondary)" }}>
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                required
                style={{ marginTop: 2 }}
              />
              <span>
                {t("login.consentPrefix")}{" "}
                <a href="/ochrana-udajov.html" target="_blank" rel="noreferrer">
                  {t("login.privacy")}
                </a>
                .
              </span>
            </label>
          )}
          {error && <div style={{ color: "var(--color-warning)", fontSize: 13 }}>{error}</div>}
          <Button type="submit" disabled={busy}>
            {mode === "login" ? t("login.submit") : t("login.createAccount")}
          </Button>
        </form>
        <button
          className="btn btn-ghost"
          style={{ marginTop: 12, fontSize: 12 }}
          onClick={() => setMode(mode === "login" ? "bootstrap" : "login")}
        >
          {mode === "login" ? t("login.firstRun") : t("login.haveAccount")}
        </button>
      </Card>
    </div>
  );
}
