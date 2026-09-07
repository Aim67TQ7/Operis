import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type Company, type Tenant } from "./api";

const KIT = "/kits/operis-epicor-discovery-0.3.0.zip";
type Measure = {
  key: string;
  status: string;
  count: number | null;
  counts: { entities: number; fields: number; custom_fields: number } | null;
};
type Finding = {
  category: string;
  subject: string;
  evidence: string;
  rationale: string;
};
type Recommendation = {
  module_code: string;
  module_name: string;
  rationale: string;
  evidence: { measurement: string; count: number }[];
};
type Run = {
  id: string;
  company_id: string;
  created_at: string;
  status: string;
  scanner_version: string;
  package_sha256: string;
};
type Assessment = Run & {
  summary: { measurements: Measure[] };
  self_evaluation: {
    coverage: { measured: number; attempted: number };
    findings: Finding[];
    recommendations: Recommendation[];
    limitations: string[];
  };
  pilot_request: { id: string; status: string } | null;
};
const labels: Record<string, string> = {
  baqs: "Business activity queries",
  bpms: "BPM methods",
  functions: "Functions",
  reports: "Reports",
  dashboards: "Dashboards",
  scheduled_tasks: "Scheduled tasks",
  ap_invoices: "Visible AP invoices",
  ap_schema: "AP invoice schema",
  vendor_schema: "Vendor schema",
  purchase_schema: "Purchasing schema",
  receipt_schema: "Receipt schema",
};
const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "Unable to complete this request.";

export function Discovery({
  tenant,
  companies,
  onExpired,
  onSetup,
}: {
  tenant: Tenant;
  companies: Company[];
  onExpired: () => void;
  onSetup: () => void;
}) {
  const [companyId, setCompanyId] = useState(companies[0]?.id || "");
  const [file, setFile] = useState<File | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const prefix = `/tenants/${tenant.id}`;
  const canWrite = tenant.role !== "viewer";
  const company = companies.find((c) => c.id === companyId);
  function fail(e: unknown) {
    if (e instanceof ApiError && e.status === 401) onExpired();
    setError(errorText(e));
  }
  useEffect(() => {
    let active = true;
    api<Run[]>(`${prefix}/discovery`)
      .then((result) => {
        if (active) setRuns(result);
      })
      .catch((e) => {
        if (active) fail(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [prefix]);
  async function show(runId: string) {
    setBusy(true);
    setError("");
    setNotice("");
    setAssessment(null);
    try {
      setAssessment(await api<Assessment>(`${prefix}/discovery/${runId}`));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file || !reviewed || !companyId) return;
    setBusy(true);
    setError("");
    setNotice("");
    setAssessment(null);
    try {
      const saved = await api<{ id: string; duplicate: boolean }>(
        `${prefix}/companies/${companyId}/discovery`,
        {
          method: "POST",
          headers: { "Content-Type": "application/zip" },
          body: file,
        },
      );
      setNotice(
        saved.duplicate
          ? "This scan was already saved. Showing its original assessment."
          : "Assessment saved. Review its coverage and findings below.",
      );
      setAssessment(await api<Assessment>(`${prefix}/discovery/${saved.id}`));
      setRuns(await api<Run[]>(`${prefix}/discovery`));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function pilot() {
    if (!assessment) return;
    setBusy(true);
    setError("");
    try {
      const request = await api<NonNullable<Assessment["pilot_request"]>>(
        `${prefix}/discovery/${assessment.id}/pilot`,
        { method: "POST", body: "{}" },
      );
      setAssessment({ ...assessment, pilot_request: request });
      setNotice(
        "Pilot request saved for your organization administrator to review. No ERP action or email was sent.",
      );
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  const report = assessment?.self_evaluation;
  return (
    <div className="discovery">
      <section className="panel discovery-intro">
        <span className="eyebrow">EPICOR DISCOVERY / ASSISTED PILOT</span>
        <h2>From your ERP to a focused next step</h2>
        <p>
          Run a limited, read-only scan inside your network. Review the
          aggregate package, upload it here, and receive an assessment with
          explicit coverage gaps.
        </p>
        <ol className="discovery-steps">
          <li>Choose company</li>
          <li>Download & run</li>
          <li>Upload & assess</li>
          <li>Request pilot</li>
        </ol>
        <p className="muted">
          This assessment does not measure GL accuracy, savings, or ERP health.
          Findings need customer validation.
        </p>
      </section>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="notice success" role="status">
          {notice}
        </div>
      )}
      {!companies.length ? (
        <section className="panel">
          <h2>Add your company first</h2>
          <p>
            The company code must match the Epicor company you intend to scan.
          </p>
          <button onClick={onSetup}>Open organization setup</button>
        </section>
      ) : (
        <section className="panel">
          <div className="panel-heading">
            <h2>1. Prepare the scan</h2>
            <span className="badge">Kit 0.3.0</span>
          </div>
          <div className="discovery-body">
            <label>
              Company to assess
              <select
                aria-label="Company to assess"
                disabled={busy}
                value={companyId}
                onChange={(e) => {
                  setCompanyId(e.target.value);
                  setFile(null);
                  setReviewed(false);
                  setAssessment(null);
                  setNotice("");
                  setError("");
                }}
              >
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code})
                  </option>
                ))}
              </select>
            </label>
            <p>
              Epicor company code: <strong>{company?.code}</strong>. Download
              both files below. Extract the kit and place{" "}
              <code>operis-scan-config.json</code> in the same folder.
            </p>
            <div className="discovery-actions">
              <a className="button-link" href={KIT} download>
                Download scanner kit
              </a>
              {canWrite && (
                <a
                  className="button-link"
                  href={`/api${prefix}/companies/${companyId}/discovery/config`}
                  download
                >
                  Download company configuration
                </a>
              )}
              <a href={`${KIT}.sha256`} download>
                SHA-256 checksum
              </a>
            </div>
            <p>
              On Windows, run <code>Run-Discovery.cmd</code>. Python 3.10+ is
              required. Enter your Epicor URL and existing credentials locally.
              Review the new ZIP in the <code>results</code> folder before
              upload.
            </p>
            <details>
              <summary>What is collected and retained?</summary>
              <p>
                The kit exports aggregate counts, coverage statuses, timestamps
                and the selected company binding. It does not export invoice
                lines, financial amounts, credentials, endpoint URLs,
                definitions or raw responses. Unsupported probes remain unknown.
                Credentials stay on your machine; the kit never uploads
                automatically.
              </p>
              <p>
                Operis accepts only the current kit format, up to 1 MiB, and
                retains validated aggregate assessments and audit history. Raw
                ZIP files are not retained. Delete the extracted kit,
                configuration and results to remove the local files.
              </p>
              <p>
                The signed configuration expires after seven days. Download a
                new one if it expires or your company code changes. Only scan an
                environment your organization authorizes.
              </p>
            </details>
          </div>
        </section>
      )}
      {company && (
        <section className="panel">
          <div className="panel-heading">
            <h2>2. Upload your results</h2>
            <span className="muted">Aggregate ZIP · maximum 1 MiB</span>
          </div>
          <div className="discovery-body">
            {canWrite ? (
              <form onSubmit={upload}>
                <label>
                  Discovery results ZIP
                  <input
                    key={companyId}
                    type="file"
                    accept=".zip,application/zip"
                    disabled={busy}
                    onChange={(e) => {
                      const next = e.target.files?.[0] || null;
                      setReviewed(false);
                      setError("");
                      if (next && next.size > 1024 * 1024) {
                        setFile(null);
                        setError(
                          "The upload limit is 1 MiB. Choose a results package from the current kit.",
                        );
                      } else setFile(next);
                    }}
                  />
                </label>
                {file && (
                  <p>
                    {file.name} · {(file.size / 1024).toFixed(1)} KiB
                  </p>
                )}
                <label className="discovery-confirm">
                  <input
                    type="checkbox"
                    checked={reviewed}
                    disabled={busy || !file}
                    onChange={(e) => setReviewed(e.target.checked)}
                  />
                  I reviewed this package and confirm it comes from the
                  authorized Epicor company shown above.
                </label>
                <button
                  className="primary"
                  disabled={busy || !file || !reviewed}
                >
                  {busy ? "Processing…" : "Upload and create assessment"}
                </button>
              </form>
            ) : (
              <p>
                You have viewing access. An administrator or operator can upload
                a scan and request a pilot.
              </p>
            )}
          </div>
        </section>
      )}
      {assessment && report?.coverage && (
        <section className="panel" aria-label="Saved assessment">
          <div className="panel-heading">
            <h2>3. Your assessment</h2>
            <a
              href={`/api${prefix}/discovery/${assessment.id}/export`}
              download
            >
              Download assessment JSON
            </a>
          </div>
          <div className="discovery-body">
            <div className="coverage">
              <strong>
                {report.coverage.measured} / {report.coverage.attempted}
              </strong>
              <div>
                <h3>Probes measured successfully</h3>
                <p>
                  {report.coverage.attempted - report.coverage.measured}{" "}
                  unavailable. Coverage is not a health score.
                </p>
              </div>
            </div>
            <p className="muted">
              Saved {new Date(assessment.created_at).toLocaleString()} · Kit{" "}
              {assessment.scanner_version}
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Measurement</th>
                    <th>Result</th>
                    <th>Coverage</th>
                  </tr>
                </thead>
                <tbody>
                  {assessment.summary.measurements.map((m) => (
                    <tr key={m.key}>
                      <td>{labels[m.key]}</td>
                      <td>
                        {m.status !== "ok"
                          ? "Unknown"
                          : m.counts
                            ? `${m.counts.entities} entities / ${m.counts.fields} fields / ${m.counts.custom_fields} custom`
                            : m.count?.toLocaleString()}
                      </td>
                      <td>{m.status.replaceAll("_", " ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3>Findings and gaps</h3>
            {report.findings.length ? (
              report.findings.map((f, i) => (
                <article className="discovery-finding" key={i}>
                  <h4>{f.subject}</h4>
                  <p>{f.evidence}</p>
                  <p className="muted">{f.rationale}</p>
                </article>
              ))
            ) : (
              <p>
                No additional findings in this limited scan. This does not
                establish that the ERP is healthy.
              </p>
            )}
            <h3>Potential pilot conversations</h3>
            {report.recommendations.length ? (
              report.recommendations.map((r) => (
                <article className="discovery-finding" key={r.module_code}>
                  <h4>{r.module_name}</h4>
                  <p>{r.rationale}</p>
                  <p className="muted">
                    Observed:{" "}
                    {r.evidence
                      .map(
                        (e) =>
                          `${labels[e.measurement]}: ${e.count.toLocaleString()}`,
                      )
                      .join("; ")}
                  </p>
                </article>
              ))
            ) : (
              <p>
                There is insufficient evidence for a module recommendation.
                Review the unavailable probes first.
              </p>
            )}
            <details>
              <summary>Assessment limitations and provenance</summary>
              <ul>
                {report.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
              <p className="mono package-digest">
                Package SHA-256: {assessment.package_sha256}
              </p>
            </details>
            <div className="pilot-panel">
              <h3>4. Request an Operis pilot</h3>
              <p>
                Ask your organization administrator to review these findings and
                agree one bounded pilot. This does not activate a module or
                authorize ERP writes.
              </p>
              {assessment.pilot_request ? (
                <p role="status">
                  Pilot request saved · {assessment.pilot_request.status}
                </p>
              ) : canWrite ? (
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => void pilot()}
                >
                  Request pilot review
                </button>
              ) : (
                <p>An administrator or operator can request a pilot.</p>
              )}
            </div>
          </div>
        </section>
      )}
      <section className="panel">
        <div className="panel-heading">
          <h2>Assessment history</h2>
          <span className="muted">Latest 100 in this organization</span>
        </div>
        <div className="discovery-body">
          {loading ? (
            <p role="status">Loading assessments…</p>
          ) : !runs.length ? (
            <p>No assessments yet. Upload your first completed scan above.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Saved</th>
                    <th>Status</th>
                    <th>Assessment</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id}>
                      <td>
                        {companies.find((c) => c.id === r.company_id)?.name ||
                          "Company unavailable"}
                      </td>
                      <td>{new Date(r.created_at).toLocaleString()}</td>
                      <td>{r.status}</td>
                      <td>
                        <button disabled={busy} onClick={() => void show(r.id)}>
                          View assessment
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
