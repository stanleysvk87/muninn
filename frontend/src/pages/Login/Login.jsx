import { useState } from "react";
import api from "../../api/client";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";

const inputStyle = {
  padding: "10px 12px",
  borderRadius: 8,
  border: "1px solid var(--color-border-strong)",
  background: "var(--color-ink-secondary)",
  color: "var(--color-text-primary)",
};

export default function Login({ onLoggedIn }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/bootstrap";
      const res = await api.post(path, { username, password });
      onLoggedIn(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Prihlasenie zlyhalo");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Card style={{ width: 360 }}>
        <div className="eyebrow">Muninn</div>
        <h1 style={{ fontSize: 22, marginTop: 8, marginBottom: 20 }}>
          {mode === "login" ? "Prihlasenie" : "Vytvorenie admin uctu"}
        </h1>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <input
            placeholder="Pouzivatelske meno"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            style={inputStyle}
          />
          <input
            type="password"
            placeholder="Heslo"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={inputStyle}
          />
          {error && <div style={{ color: "var(--color-warning)", fontSize: 13 }}>{error}</div>}
          <Button type="submit" disabled={busy}>
            {mode === "login" ? "Prihlasit sa" : "Vytvorit ucet"}
          </Button>
        </form>
        <button
          className="btn btn-ghost"
          style={{ marginTop: 12, fontSize: 12 }}
          onClick={() => setMode(mode === "login" ? "bootstrap" : "login")}
        >
          {mode === "login" ? "Prve spustenie? Vytvorit admin ucet" : "Uz mam ucet"}
        </button>
      </Card>
    </div>
  );
}
