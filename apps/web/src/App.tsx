import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  api,
  ApiError,
  type AuditEvent,
  type Identity,
  type Tenant,
  type Workspace,
} from "./api";

type Page = "Workspace" | "Organization" | "Connections" | "Activity";
const pages: Page[] = ["Workspace", "Organization", "Connections", "Activity"];
const symbols: Record<Page, string> = {
  Workspace: "◫",
  Organization: "▦",
  Connections: "⇄",
  Activity: "≡",
};
const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "Something went wrong. Please try again.";
const utc = (value: string) =>
  new Date(value).toLocaleString(undefined, {
    timeZone: "UTC",
    dateStyle: "medium",
    timeStyle: "short",
  }) + " UTC";

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">
        O
      </span>
      <span>
        OPERIS<small>INTELLIGENCE LAYER</small>
      </span>
    </div>
  );
}
function Notice({
  children,
  kind = "error",
}: {
  children: ReactNode;
  kind?: "error" | "success";
}) {
  return (
    <div
      className={`notice ${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-glyph" aria-hidden="true">
        ◇
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

function SignIn({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [usePassword, setUsePassword] = useState(false);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (usePassword) {
        await api("/auth/password", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        onSuccess();
      } else if (sent) {
        await api("/auth/verify", {
          method: "POST",
          body: JSON.stringify({ email, code }),
        });
        setCode("");
        onSuccess();
      } else {
        await api("/auth/code", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
        setSent(true);
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setPassword("");
      setBusy(false);
    }
  }
  return (
    <div className="signin">
      <aside className="signin-aside">
        <Brand />
        <div>
          <span className="eyebrow">YOUR OPERATING WORKSPACE</span>
          <h1>
            One interface.
            <br />
            Full context.
          </h1>
          <p>Your systems, working as one.</p>
        </div>
        <small>OPERIS / FOUNDATION</small>
      </aside>
      <main className="signin-main">
        <form onSubmit={submit} className="login-form">
          <span className="eyebrow">SECURE ACCESS</span>
          <h2>{sent ? "Check your email" : "Sign in to Operis"}</h2>
          <p>
            {sent
              ? "Open the sign-in link in your email using this same browser. If the email includes a code instead, enter it below."
              : "Use the email associated with your organization."}
          </p>
          {error && <Notice>{error}</Notice>}
          <label>
            Email address
            <input
              autoComplete="email"
              type="email"
              required
              maxLength={254}
              value={email}
              disabled={sent || busy}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          {usePassword && (
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                required
                maxLength={256}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
          )}
          {sent && (
            <label>
              Sign-in code
              <input
                autoFocus
                autoComplete="one-time-code"
                inputMode="numeric"
                pattern="[0-9]{6,10}"
                minLength={6}
                maxLength={10}
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
          )}
          <button className="primary" disabled={busy}>
            {busy
              ? "Please wait…"
              : usePassword
                ? "Sign in with password"
                : sent
                  ? "Enter workspace"
                  : "Send sign-in link"}
            <span aria-hidden="true">→</span>
          </button>
          {sent && (
            <button
              type="button"
              className="text-button"
              disabled={busy}
              onClick={() => {
                setSent(false);
                setCode("");
                setError("");
              }}
            >
              Use another email or request a new link
            </button>
          )}
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => {
              setUsePassword(!usePassword);
              setSent(false);
              setCode("");
              setPassword("");
              setError("");
            }}
          >
            {usePassword
              ? "Forgot password? Sign in with an email link"
              : "Use a password instead"}
          </button>
          <p className="login-note">
            Access is managed by your organization administrator.
          </p>
        </form>
      </main>
    </div>
  );
}

function Audit({
  events,
  userId,
  compact = false,
}: {
  events: AuditEvent[];
  userId: string;
  compact?: boolean;
}) {
  if (!events.length)
    return (
      <Empty title="No changes recorded yet">
        Organization changes will appear here with their supporting details.
      </Empty>
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Change</th>
            <th>Actor</th>
            {!compact && <th>Evidence</th>}
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td className="muted nowrap">{utc(event.created_at)}</td>
              <td>
                <strong>
                  {event.action === "INSERT" ? "Created" : "Updated"}{" "}
                  {event.table_name.replace("operis_", "").replaceAll("_", " ")}
                </strong>
                <small className="record-id">
                  {String(
                    event.after?.name || event.after?.code || event.record_id,
                  )}
                </small>
              </td>
              <td>
                <span title={event.actor_id || "Platform operator"}>
                  {event.actor_id === userId
                    ? "You"
                    : event.actor_id?.slice(0, 8) || "Platform operator"}
                </span>
              </td>
              {!compact && (
                <td>
                  <details>
                    <summary>View changes</summary>
                    <div className="evidence">
                      <p>Record: {event.record_id}</p>
                      <p>
                        Request: {event.request_id || "Operator provisioning"}
                      </p>
                      <strong>Before</strong>
                      <pre>{JSON.stringify(event.before, null, 2)}</pre>
                      <strong>After</strong>
                      <pre>{JSON.stringify(event.after, null, 2)}</pre>
                    </div>
                  </details>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Organization({
  tenant,
  data,
  mutate,
  busy,
}: {
  tenant: Tenant;
  data: Workspace;
  mutate: (path: string, method: string, body: unknown) => Promise<boolean>;
  busy: boolean;
}) {
  const [name, setName] = useState(tenant.name);
  const [companyCode, setCompanyCode] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [siteCode, setSiteCode] = useState("");
  const [siteName, setSiteName] = useState("");
  const [companyId, setCompanyId] = useState("");
  const admin = data.role === "admin";
  useEffect(() => setName(tenant.name), [tenant.name]);
  async function addCompany(e: FormEvent) {
    e.preventDefault();
    if (
      await mutate("/companies", "POST", {
        code: companyCode,
        name: companyName,
      })
    ) {
      setCompanyCode("");
      setCompanyName("");
    }
  }
  async function addSite(e: FormEvent) {
    e.preventDefault();
    if (
      await mutate("/sites", "POST", {
        code: siteCode,
        name: siteName,
        company_id: companyId,
      })
    ) {
      setSiteCode("");
      setSiteName("");
    }
  }
  return (
    <>
      <section className="panel">
        <div className="panel-heading">
          <h2>Organization details</h2>
          <span className="badge">{data.role}</span>
        </div>
        {admin ? (
          <form
            className="inline-form"
            onSubmit={async (e) => {
              e.preventDefault();
              await mutate("", "PATCH", { name });
            }}
          >
            <label>
              Organization name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                minLength={2}
                maxLength={100}
              />
            </label>
            <button disabled={busy || name === tenant.name}>Save name</button>
          </form>
        ) : (
          <p className="panel-copy">
            {tenant.name} · Contact an administrator to change organization
            settings.
          </p>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Companies</h2>
          <span className="count">{data.companies.length}</span>
        </div>
        {data.companies.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Company name</th>
                  <th>Sites</th>
                </tr>
              </thead>
              <tbody>
                {data.companies.map((c) => (
                  <tr key={c.id}>
                    <td className="mono">{c.code}</td>
                    <td>{c.name}</td>
                    <td>
                      {data.sites.filter((s) => s.company_id === c.id).length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="Add your first company">
            Define the legal entities within this organization.
          </Empty>
        )}
        {admin && (
          <form className="inline-form" onSubmit={addCompany}>
            <label>
              Company code
              <input
                required
                maxLength={24}
                pattern="[A-Za-z0-9_-]+"
                value={companyCode}
                onChange={(e) => setCompanyCode(e.target.value)}
              />
            </label>
            <label>
              Company name
              <input
                required
                minLength={2}
                maxLength={100}
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
              />
            </label>
            <button disabled={busy}>Add company</button>
          </form>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Sites & facilities</h2>
          <span className="count">{data.sites.length}</span>
        </div>
        {data.sites.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Site name</th>
                  <th>Company</th>
                </tr>
              </thead>
              <tbody>
                {data.sites.map((s) => (
                  <tr key={s.id}>
                    <td className="mono">{s.code}</td>
                    <td>{s.name}</td>
                    <td>
                      {data.companies.find((c) => c.id === s.company_id)
                        ?.name || s.company_id}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="No sites added">
            Each facility belongs to a company in your organization.
          </Empty>
        )}
        {admin && data.companies.length > 0 && (
          <form className="inline-form" onSubmit={addSite}>
            <label>
              Company
              <select
                required
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
              >
                <option value="">Select company</option>
                {data.companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Site code
              <input
                required
                maxLength={24}
                pattern="[A-Za-z0-9_-]+"
                value={siteCode}
                onChange={(e) => setSiteCode(e.target.value)}
              />
            </label>
            <label>
              Site name
              <input
                required
                minLength={2}
                maxLength={100}
                value={siteName}
                onChange={(e) => setSiteName(e.target.value)}
              />
            </label>
            <button disabled={busy}>Add site</button>
          </form>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Workspace access</h2>
          <span className="muted">Managed by platform administrator</span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>User identity</th>
                <th>Role</th>
              </tr>
            </thead>
            <tbody>
              {data.memberships.map((m) => (
                <tr key={m.user_id}>
                  <td className="mono">{m.user_id}</td>
                  <td>
                    <span className="badge">{m.role}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function PasswordSettings() {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    setDone(false);
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await api("/auth/password", {
        method: "PUT",
        body: JSON.stringify({ password }),
      });
      setDone(true);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
      setPassword("");
      setConfirm("");
    }
  }
  return (
    <details className="panel">
      <summary>Account password</summary>
      <p>
        Set or change your shared ZODA account password. This also changes the
        password used by other apps connected to this account.
      </p>
      <p>
        Use at least 12 characters. If you forget it, sign in with an email link
        and return here.
      </p>
      {error && <Notice>{error}</Notice>}
      {done && (
        <Notice kind="success">
          Password saved. You can now sign in with your email and password.
        </Notice>
      )}
      <form className="login-form" onSubmit={save}>
        <label>
          New password
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={256}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <label>
          Confirm new password
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={256}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        <button disabled={busy}>
          {busy ? "Saving…" : "Save shared account password"}
        </button>
      </form>
    </details>
  );
}

export function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [tenantId, setTenantId] = useState("");
  const [page, setPage] = useState<Page>("Workspace");
  const [data, setData] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const tenant = identity?.tenants.find((t) => t.id === tenantId);
  async function loadIdentity() {
    setLoading(true);
    setError("");
    try {
      const next = await api<Identity>("/me");
      setIdentity(next);
      setTenantId((current) =>
        next.tenants.some((t) => t.id === current)
          ? current
          : next.tenants[0]?.id || "",
      );
    } catch (e) {
      setIdentity(null);
      if (!(e instanceof ApiError && e.status === 401)) setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void loadIdentity();
  }, []);
  async function loadWorkspace(id: string) {
    const version = ++generation.current;
    setData(null);
    setError("");
    try {
      const result = await api<Workspace>(`/tenants/${id}/workspace`);
      if (version === generation.current) {
        setData(result);
        return true;
      }
      return false;
    } catch (e) {
      if (version !== generation.current) return false;
      if (e instanceof ApiError && e.status === 401) {
        setIdentity(null);
        setTenantId("");
        setError("Your session has expired. Sign in again to continue.");
      } else setError(errorText(e));
      return false;
    }
  }
  useEffect(() => {
    setSuccess("");
    if (tenantId) void loadWorkspace(tenantId);
    return () => {
      generation.current++;
    };
  }, [tenantId]);
  async function mutate(path: string, method: string, body: unknown) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api(`/tenants/${tenantId}${path}`, {
        method,
        body: JSON.stringify(body),
      });
      if (path === "") {
        const updated = await api<Identity>("/me");
        setIdentity(updated);
      }
      const refreshed = await loadWorkspace(tenantId);
      setSuccess(
        refreshed
          ? "Change saved. The audit history has been updated."
          : "Change saved, but the workspace could not be refreshed. Use Refresh before making another change.",
      );
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setIdentity(null);
        setTenantId("");
      }
      setError(errorText(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function signOut() {
    setBusy(true);
    try {
      const result = await api<{ provider_revoked?: boolean }>("/auth/logout", {
        method: "POST",
        body: "{}",
      });
      generation.current++;
      setIdentity(null);
      setData(null);
      setTenantId("");
      setSuccess("");
      setPage("Workspace");
      setError(
        result.provider_revoked === false
          ? "You are signed out of this browser. The identity service was unavailable, so remote session revocation could not be confirmed."
          : "",
      );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  if (loading)
    return (
      <main className="boot" role="status">
        <Brand />
        <p>Opening your workspace…</p>
      </main>
    );
  if (!identity)
    return (
      <>
        {error && (
          <div className="global-error">
            <Notice>
              {error} <button onClick={() => void loadIdentity()}>Retry</button>
            </Notice>
          </div>
        )}
        <SignIn onSuccess={() => void loadIdentity()} />
      </>
    );
  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Brand />
        <div className="rail-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {pages.map((p) => (
            <button
              key={p}
              aria-current={page === p ? "page" : undefined}
              onClick={() => {
                setPage(p);
                setSuccess("");
              }}
            >
              <span aria-hidden="true">{symbols[p]}</span>
              {p}
            </button>
          ))}
        </nav>
        <div className="rail-bottom">
          <span className="avatar" aria-hidden="true">
            {identity.user.email.slice(0, 2).toUpperCase()}
          </span>
          <div className="user-email" title={identity.user.email}>
            {identity.user.email}
          </div>
          <button
            className="signout"
            onClick={() => void signOut()}
            disabled={busy}
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb">
            Operis <span>/</span> {page}
          </div>
          <label className="tenant-picker">
            <span className="sr-only">Organization</span>
            <select
              value={tenantId}
              disabled={busy}
              onChange={(e) => {
                generation.current++;
                setData(null);
                setTenantId(e.target.value);
              }}
            >
              {!identity.tenants.length && (
                <option value="">No organization</option>
              )}
              {identity.tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <span className="badge">{tenant?.role || "No access"}</span>
        </header>
        <main id="main" className="content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {tenant?.name || "ORGANIZATION ACCESS"}
              </span>
              <h1>{page}</h1>
              <p>
                {
                  {
                    Workspace: "Your organization at a glance.",
                    Organization: "Define your company and facility structure.",
                    Connections: "Bring your operational systems into Operis.",
                    Activity: "A traceable record of organization changes.",
                  }[page]
                }
              </p>
            </div>
            {tenant && (
              <button
                disabled={busy}
                onClick={() => void loadWorkspace(tenantId)}
              >
                ↻ Refresh
              </button>
            )}
          </div>
          {error && <Notice>{error}</Notice>}
          {success && <Notice kind="success">{success}</Notice>}
          <PasswordSettings />
          {!tenant ? (
            <section className="panel">
              <Empty title="Your account is verified">
                An administrator needs to assign you to an organization before
                you can enter its workspace.
              </Empty>
              <button
                className="access-refresh"
                onClick={() => void loadIdentity()}
              >
                Check access again
              </button>
            </section>
          ) : !data ? (
            <section className="panel">
              <p className="panel-copy" role="status">
                {error
                  ? "Workspace data could not be loaded. Use Refresh to try again."
                  : "Loading organization…"}
              </p>
            </section>
          ) : (
            <>
              {page === "Workspace" && (
                <>
                  <div className="stats">
                    {[
                      ["Companies", data.companies.length],
                      ["Sites & facilities", data.sites.length],
                      ["Workspace members", data.memberships.length],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <span>{label}</span>
                        <strong>{value}</strong>
                      </div>
                    ))}
                  </div>
                  <section className="panel">
                    <div className="panel-heading">
                      <h2>Workspace setup</h2>
                      <span className="badge">Foundation</span>
                    </div>
                    <div className="setup-row">
                      <span className="step">01</span>
                      <div>
                        <h3>Define your organization</h3>
                        <p>
                          Add the companies and facilities your team works
                          across.
                        </p>
                      </div>
                      <button onClick={() => setPage("Organization")}>
                        Manage organization →
                      </button>
                    </div>
                    <div className="setup-row">
                      <span className="step">02</span>
                      <div>
                        <h3>Connect your systems</h3>
                        <p>
                          Connector setup and existing module integration follow
                          in Phase 2.
                        </p>
                      </div>
                      <span className="badge">Planned</span>
                    </div>
                    <div className="setup-row">
                      <span className="step">03</span>
                      <div>
                        <h3>Activate operational modules</h3>
                        <p>
                          Modules become available after their sources and
                          access rules are validated.
                        </p>
                      </div>
                      <span className="badge">Planned</span>
                    </div>
                  </section>
                  <section className="panel">
                    <div className="panel-heading">
                      <h2>Recent activity</h2>
                      <button
                        className="text-button"
                        onClick={() => setPage("Activity")}
                      >
                        View all →
                      </button>
                    </div>
                    <Audit
                      events={data.audit_events.slice(0, 5)}
                      userId={identity.user.id}
                      compact
                    />
                  </section>
                </>
              )}
              {page === "Organization" && (
                <Organization
                  key={tenantId}
                  tenant={tenant}
                  data={data}
                  mutate={mutate}
                  busy={busy}
                />
              )}
              {page === "Connections" && (
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Connected systems</h2>
                    <span className="badge">Phase 2</span>
                  </div>
                  <Empty title="System connections are not enabled yet">
                    This workspace currently manages your organization
                    structure. Connector discovery and the existing Lovable
                    modules will be added in Phase 2.
                  </Empty>
                </section>
              )}
              {page === "Activity" && (
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Organization audit history</h2>
                    <span className="muted">Most recent 200 events · UTC</span>
                  </div>
                  <Audit events={data.audit_events} userId={identity.user.id} />
                </section>
              )}
              <p className="data-note">
                Organization lists show up to 200 records. Operational data
                sources are not connected.
              </p>
            </>
          )}
          <footer>
            OPERIS <span>ONE INTERFACE. FULL CONTEXT.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
