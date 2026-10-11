import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function App() {
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    fetch("/api/health/")
      .then((r) => r.json())
      .then((d) => setStatus(d.status ?? "unknown"))
      .catch(() => setStatus("offline"));
  }, []);

  return (
    <main className="shell">
      <section className="card">
        <span className="eyebrow">SELF-HOSTED PROJECT MANAGEMENT</span>
        <h1>Taskautomation</h1>
        <p>
          Django and React are running from one deployable repository.
          PostgreSQL, migrations, static files and initial admin creation
          are handled automatically by Docker Compose.
        </p>

        <div className="status">
          <span className={"dot " + status}></span>
          API status: <strong>{status}</strong>
        </div>

        <div className="actions">
          <a className="primary" href="/admin/">Open administration</a>
          <a href="/api/health/">API health</a>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
