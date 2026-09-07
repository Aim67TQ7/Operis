const form = document.querySelector("#checks");
const status = document.querySelector("#status");
const report = document.querySelector("#report");
const lost = document.querySelector("#lost");
let results = [];
let viewerId;
const render = () => {
  report.textContent = JSON.stringify(
    { checked_at: new Date().toISOString(), results },
    null,
    2,
  );
};
function check(label, ok, evidence = {}) {
  results.push({ check: label, result: ok ? "passed" : "failed", ...evidence });
  render();
  if (!ok) throw new Error(label);
}
async function request(label, path, expected, method = "GET", body) {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const payload = await response.json();
  check(label, response.status === expected, {
    status: response.status,
    request_id: response.headers.get("x-request-id"),
  });
  check(
    label + ": no-store and correlation",
    response.headers.get("cache-control") === "no-store" &&
      Boolean(response.headers.get("x-request-id")),
  );
  check(
    label + ": response contains no session tokens",
    !/"(?:access_token|refresh_token|id_token)"\s*:/.test(
      JSON.stringify(payload),
    ),
  );
  return payload;
}
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  form.querySelector("button").disabled = true;
  lost.disabled = true;
  results = [];
  status.textContent = "Running";
  try {
    check(
      "Approved staging origin",
      location.origin === "https://operis-staging.netlify.app",
    );
    const input = Object.fromEntries(new FormData(form));
    check(
      "Fixture IDs are UUIDs",
      Object.values(input).every((value) => /^[a-f0-9-]{36}$/i.test(value)),
    );
    const identity = await request("Authenticated identity", "/me", 200);
    check(
      "Admin fixture role",
      identity.tenants.some((t) => t.id === input.admin && t.role === "admin"),
    );
    check(
      "Viewer fixture role",
      identity.tenants.some(
        (t) =>
          t.id === input.viewer &&
          t.role === "viewer" &&
          t.name === "Operis PR1 QA Viewer",
      ),
    );
    check(
      "Private fixture absent from tenant list",
      !identity.tenants.some((t) => t.id === input.private),
    );
    check(
      "No JavaScript-visible session or PKCE cookie",
      !document.cookie
        .split(";")
        .some((c) => /^\s*(?:__Host-)?operis_(?:session|pkce)=/.test(c)),
    );
    check("No localStorage persistence", localStorage.length === 0);
    check("No sessionStorage persistence", sessionStorage.length === 0);
    await request("Admin workspace", `/tenants/${input.admin}/workspace`, 200);
    const before = await request(
      "Viewer workspace",
      `/tenants/${input.viewer}/workspace`,
      200,
    );
    check("Viewer response is read-only role", before.role === "viewer");
    await request(
      "Existing private workspace denied",
      `/tenants/${input.private}/workspace`,
      404,
    );
    const ownCompany = before.companies.find((c) => c.code === "QA-VIEWER");
    check("Viewer company fixture exists", Boolean(ownCompany));
    for (const [label, tenant, expected, company] of [
      ["Viewer", input.viewer, 403, ownCompany.id],
      ["Cross-tenant", input.private, 404, input.company],
    ]) {
      await request(
        label + " rename denied",
        `/tenants/${tenant}`,
        expected,
        "PATCH",
        { name: "Denied PR1 QA rename" },
      );
      await request(
        label + " company denied",
        `/tenants/${tenant}/companies`,
        expected,
        "POST",
        { code: "PR1-DENIED", name: "Denied PR1 QA company" },
      );
      await request(
        label + " site denied",
        `/tenants/${tenant}/sites`,
        expected,
        "POST",
        { company_id: company, code: "PR1-DENIED", name: "Denied PR1 QA site" },
      );
    }
    await request(
      "Cross-tenant company relationship denied to admin",
      `/tenants/${input.admin}/sites`,
      404,
      "POST",
      {
        company_id: input.company,
        code: "PR1-DENIED",
        name: "Denied PR1 cross-company site",
      },
    );
    const after = await request(
      "Viewer workspace after denials",
      `/tenants/${input.viewer}/workspace`,
      200,
    );
    check(
      "Rejected writes leave data and audit unchanged",
      JSON.stringify(before) === JSON.stringify(after),
    );
    viewerId = input.viewer;
    lost.disabled = false;
    status.textContent = "All authenticated boundary checks passed";
  } catch (error) {
    status.textContent = "Failed: " + error.message;
  } finally {
    form.querySelector("button").disabled = false;
    render();
  }
});
lost.addEventListener("click", async () => {
  lost.disabled = true;
  try {
    await request(
      "Removed viewer membership denied immediately",
      `/tenants/${viewerId}/workspace`,
      404,
    );
    const identity = await request(
      "Identity after membership removal",
      "/me",
      200,
    );
    check(
      "Removed tenant absent from identity",
      !identity.tenants.some((t) => t.id === viewerId),
    );
    status.textContent = "Membership removal checks passed";
  } catch (error) {
    status.textContent = "Failed: " + error.message;
  } finally {
    lost.disabled = false;
    render();
  }
});
