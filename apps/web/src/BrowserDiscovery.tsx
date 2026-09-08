import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "./api";

type Measurement = {
  key: string;
  status: string;
  count: number | null;
  counts: { entities: number; fields: number; custom_fields: number } | null;
};
type Preview = {
  receipt: {
    payload: { summary: { measurements: Measurement[] }; expires_at: number };
    signature: string;
  };
  report: {
    coverage: { measured: number; attempted: number };
    limitations: string[];
  };
};
export function BrowserDiscovery({
  prefix,
  companyId,
  onSaved,
  onExpired,
}: {
  prefix: string;
  companyId: string;
  onSaved: (id: string) => Promise<void>;
  onExpired: () => void;
}) {
  const [endpoint, setEndpoint] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [consent, setConsent] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [phase, setPhase] = useState<
    "idle" | "checking" | "running" | "saving" | "saved"
  >("idle");
  const [error, setError] = useState("");
  const [savedId, setSavedId] = useState("");
  const active = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const path = `${prefix}/companies/${companyId}/discovery/browser`;
  const busy =
    phase === "running" || phase === "saving" || phase === "checking";
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      controller.current?.abort();
    };
  }, []);
  function fail(e: unknown) {
    if (!active.current) return;
    if (e instanceof ApiError && e.status === 401) onExpired();
    setError(
      e instanceof Error ? e.message : "Discovery failed. Nothing was saved.",
    );
  }
  async function setup() {
    setPhase("checking");
    setError("");
    controller.current = new AbortController();
    try {
      const result = await api<{ endpoint: string }>(path, {
        signal: controller.current.signal,
      });
      if (active.current) setEndpoint(result.endpoint);
    } catch (e) {
      fail(e);
    } finally {
      if (active.current) setPhase("idle");
    }
  }
  async function run(e: FormEvent) {
    e.preventDefault();
    if (!consent || busy) return;
    setPhase("running");
    setError("");
    setPreview(null);
    setSavedId("");
    const body = JSON.stringify({ username, password, api_key: apiKey });
    setUsername("");
    setPassword("");
    setApiKey("");
    const operation = new AbortController();
    controller.current = operation;
    try {
      const result = await api<Preview>(`${path}/run`, {
        method: "POST",
        body,
        signal: operation.signal,
      });
      if (active.current && !operation.signal.aborted) setPreview(result);
    } catch (e) {
      if (!operation.signal.aborted) fail(e);
    } finally {
      if (active.current) {
        setPhase("idle");
        setConsent(false);
      }
    }
  }
  async function save() {
    if (!preview || busy) return;
    setPhase("saving");
    setError("");
    controller.current = new AbortController();
    try {
      const result = await api<{ id: string }>(`${path}/save`, {
        method: "POST",
        body: JSON.stringify(preview.receipt),
        signal: controller.current.signal,
      });
      if (!active.current) return;
      setSavedId(result.id);
      setPreview(null);
      setPhase("saved");
      await onSaved(result.id);
    } catch (e) {
      fail(e);
    } finally {
      if (active.current) setPhase((p) => (p === "saved" ? p : "idle"));
    }
  }
  return (
    <section className="panel" aria-label="Browser discovery">
      <div className="panel-heading">
        <h2>Run discovery in your browser</h2>
        <span className="badge">Read-only</span>
      </div>
      <div className="discovery-body">
        <p>
          No downloads or installation. Operis reads eleven company-wide counts
          and schema measurements from the configured Epicor system. Review the
          results before saving an assessment.
        </p>
        {error && (
          <p role="alert" className="notice error">
            {error}
          </p>
        )}
        {!endpoint ? (
          <button
            className="primary"
            disabled={busy}
            onClick={() => void setup()}
          >
            {phase === "checking"
              ? "Checking connection setup…"
              : "Set up browser scan"}
          </button>
        ) : (
          <>
            <p>
              Epicor connection: <strong>{endpoint}</strong>
            </p>
            <p>
              Enter an existing Epicor account and API key authorized for this
              company. Credentials are sent securely to Operis for this scan,
              are not saved, and are cleared from the form when the scan starts.
              No invoice lines, amounts or raw definitions are retained. This
              scan is company-wide; it does not filter by site.
            </p>
            {!preview && !savedId && (
              <form onSubmit={run} autoComplete="off">
                <label>
                  Epicor username
                  <input
                    required
                    maxLength={256}
                    value={username}
                    disabled={busy}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label>
                  Epicor password
                  <input
                    required
                    type="password"
                    maxLength={512}
                    value={password}
                    disabled={busy}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label>
                  Epicor API key
                  <input
                    required
                    type="password"
                    maxLength={2048}
                    value={apiKey}
                    disabled={busy}
                    onChange={(e) => setApiKey(e.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label className="discovery-confirm">
                  <input
                    type="checkbox"
                    checked={consent}
                    disabled={busy}
                    onChange={(e) => setConsent(e.target.checked)}
                  />
                  I authorize this read-only scan and the collection of
                  aggregate results by Operis.
                </label>
                <button className="primary" disabled={busy || !consent}>
                  {phase === "running"
                    ? "Reading Epicor…"
                    : "Run read-only discovery"}
                </button>
                {phase === "running" && (
                  <>
                    <p role="status">
                      Checking the company and reading counts and schemas. This
                      normally takes less than 25 seconds.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        controller.current?.abort();
                        setError(
                          "Scan cancelled. No assessment was saved. Any reads already started will finish within the scan time limit.",
                        );
                      }}
                    >
                      Cancel scan
                    </button>
                  </>
                )}
              </form>
            )}
            {preview && (
              <div aria-label="Discovery preview" role="region">
                <h3>Review before saving</h3>
                <p>
                  {preview.report.coverage.measured} /{" "}
                  {preview.report.coverage.attempted} probes measured.
                  Unavailable results are unknown, not a healthy finding.
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Measurement</th>
                        <th>Result</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.receipt.payload.summary.measurements.map((m) => (
                        <tr key={m.key}>
                          <td>{m.key.replaceAll("_", " ")}</td>
                          <td>
                            {m.status !== "ok"
                              ? "Unknown"
                              : m.counts
                                ? `${m.counts.entities} entities / ${m.counts.fields} fields / ${m.counts.custom_fields} custom`
                                : m.count}
                          </td>
                          <td>{m.status.replaceAll("_", " ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p>
                  Only the displayed aggregates and assessment will be saved
                  with audit history. This preview expires after 30 minutes.
                </p>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => void save()}
                >
                  {phase === "saving"
                    ? "Saving assessment…"
                    : "Save assessment"}
                </button>
                <button disabled={busy} onClick={() => setPreview(null)}>
                  Discard results
                </button>
              </div>
            )}
            {savedId && (
              <p role="status">
                Assessment saved.{" "}
                <button onClick={() => void onSaved(savedId).catch(fail)}>
                  View saved assessment
                </button>
                <button
                  onClick={() => {
                    setSavedId("");
                    setPhase("idle");
                  }}
                >
                  Start another scan
                </button>
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
