import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

const identity = {
  user: { id: "user-a", email: "admin@example.com" },
  tenants: [
    { id: "tenant-a", name: "Alpha organization", role: "admin" },
    { id: "tenant-b", name: "Beta organization", role: "viewer" },
  ],
};
const workspace = {
  role: "admin",
  companies: [],
  sites: [],
  memberships: [{ user_id: "user-a", role: "admin" }],
  audit_events: [],
};
function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Request-ID": "test-id" },
  });
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("sign-in uses email/code and cookie requests without storing tokens", async () => {
  let signedIn = false;
  const requests: { path: string; options: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options: RequestInit) => {
      requests.push({ path, options });
      if (path === "/api/auth/code")
        return response({ message: "Check email" }, 202);
      if (path === "/api/auth/verify") {
        signedIn = true;
        return response({ authenticated: true });
      }
      if (path === "/api/me")
        return signedIn
          ? response(identity)
          : response({ detail: "Sign in" }, 401);
      return response(workspace);
    }),
  );
  const storage = vi.spyOn(Storage.prototype, "setItem");
  const user = userEvent.setup();
  render(<App />);
  await user.type(
    await screen.findByLabelText("Email address"),
    "admin@example.com",
  );
  await user.click(screen.getByRole("button", { name: /Send sign-in link/ }));
  await user.type(await screen.findByLabelText("Sign-in code"), "123456");
  await user.click(screen.getByRole("button", { name: /Enter workspace/ }));
  await screen.findByRole("heading", { name: "Workspace setup" });
  expect(requests.every((r) => r.options.credentials === "same-origin")).toBe(
    true,
  );
  expect(storage).not.toHaveBeenCalled();
  storage.mockRestore();
});

test("organization form saves to active tenant and reloads server data", async () => {
  let created = false;
  const fetcher = vi.fn(async (path: string, _options: RequestInit) => {
    if (path === "/api/me") return response(identity);
    if (path === "/api/tenants/tenant-a/companies") {
      created = true;
      return response({ id: "company-a" }, 201);
    }
    return response({
      ...workspace,
      companies: created
        ? [{ id: "company-a", code: "ACME", name: "Acme Manufacturing" }]
        : [],
    });
  });
  vi.stubGlobal("fetch", fetcher);
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("heading", { name: "Workspace setup" });
  await user.click(screen.getByRole("button", { name: "Organization" }));
  await user.type(screen.getByLabelText("Company code"), "ACME");
  await user.type(screen.getByLabelText("Company name"), "Acme Manufacturing");
  await user.click(screen.getByRole("button", { name: "Add company" }));
  expect(
    await screen.findByRole("cell", { name: "Acme Manufacturing" }),
  ).toBeTruthy();
  const write = fetcher.mock.calls.find(([path]) =>
    path.endsWith("/companies"),
  )!;
  expect(JSON.parse(write[1].body as string)).toEqual({
    code: "ACME",
    name: "Acme Manufacturing",
  });
});

test("switching tenants clears prior data while new request is pending", async () => {
  let resolveBeta: (value: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/me") return response(identity);
      if (path.includes("tenant-b"))
        return new Promise<Response>((resolve) => {
          resolveBeta = resolve;
        });
      return response({
        ...workspace,
        companies: [{ id: "a", code: "A", name: "Alpha private company" }],
      });
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("heading", { name: "Workspace setup" });
  await user.click(screen.getByRole("button", { name: "Organization" }));
  expect(
    screen.getByRole("cell", { name: "Alpha private company" }),
  ).toBeTruthy();
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Organization" }),
    "tenant-b",
  );
  expect(screen.queryByText("Alpha private company")).toBeNull();
  resolveBeta(response({ ...workspace, role: "viewer", companies: [] }));
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "Organization details" }),
    ).toBeTruthy(),
  );
  expect(screen.queryByRole("button", { name: "Add company" })).toBeNull();
});

test("backend failure is visible and never masquerades as an empty workspace", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      path === "/api/me"
        ? response(identity)
        : response({ detail: "Service unavailable" }, 503),
    ),
  );
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Service unavailable",
  );
  expect(screen.queryByRole("heading", { name: "Workspace setup" })).toBeNull();
});

test("verified users without membership see no tenant data or creation shortcut", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response({ ...identity, tenants: [] })),
  );
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Your account is verified" }),
  ).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Add company" })).toBeNull();
});

test("password settings require matching confirmation and clear saved fields", async () => {
  const fetcher = vi.fn(async (path: string) =>
    response(
      path === "/api/me"
        ? identity
        : path === "/api/auth/password"
          ? { updated: true }
          : workspace,
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("heading", { name: "Workspace setup" });
  await user.click(screen.getByText("Account password"));
  await user.type(screen.getByLabelText("New password"), "test-password-123");
  await user.type(
    screen.getByLabelText("Confirm new password"),
    "test-password-456",
  );
  await user.click(
    screen.getByRole("button", { name: "Save shared account password" }),
  );
  expect(await screen.findByText("Passwords do not match.")).toBeTruthy();
  expect(
    fetcher.mock.calls.some(([path]) => path === "/api/auth/password"),
  ).toBe(false);
  await user.clear(screen.getByLabelText("Confirm new password"));
  await user.type(
    screen.getByLabelText("Confirm new password"),
    "test-password-123",
  );
  await user.click(
    screen.getByRole("button", { name: "Save shared account password" }),
  );
  expect(await screen.findByText(/Password saved/)).toBeTruthy();
  expect(
    (screen.getByLabelText("New password") as HTMLInputElement).value,
  ).toBe("");
});

test("site creation survives remount and exposes actor, before/after and request evidence", async () => {
  const company = { id: "company-a", code: "ACME", name: "Acme Manufacturing" };
  const site = {
    id: "site-a",
    company_id: company.id,
    code: "NORTH",
    name: "North facility",
  };
  let saved = false;
  const fetcher = vi.fn(async (path: string, options: RequestInit) => {
    if (path === "/api/me") return response(identity);
    if (path.endsWith("/sites")) {
      expect(JSON.parse(options.body as string)).toEqual({
        company_id: company.id,
        code: site.code,
        name: site.name,
      });
      saved = true;
      return response(site, 201);
    }
    return response({
      ...workspace,
      companies: [company],
      sites: saved ? [site] : [],
      audit_events: saved
        ? [
            {
              id: "audit-site",
              actor_id: identity.user.id,
              action: "INSERT",
              table_name: "operis_sites",
              record_id: site.id,
              before: null,
              after: site,
              request_id: "request-site",
              created_at: "2026-09-06T12:00:00Z",
            },
          ]
        : [],
    });
  });
  vi.stubGlobal("fetch", fetcher);
  const user = userEvent.setup();
  const first = render(<App />);
  await screen.findByRole("heading", { name: "Workspace setup" });
  await user.click(screen.getByRole("button", { name: "Organization" }));
  await user.selectOptions(
    screen.getByLabelText("Company", { exact: true }),
    company.id,
  );
  await user.type(screen.getByLabelText("Site code"), site.code);
  await user.type(screen.getByLabelText("Site name"), site.name);
  await user.click(screen.getByRole("button", { name: "Add site" }));
  await screen.findByRole("cell", { name: site.name });
  first.unmount();
  render(<App />);
  await screen.findByRole("heading", { name: "Workspace setup" });
  await user.click(screen.getByRole("button", { name: "Organization" }));
  expect(screen.getByRole("cell", { name: site.name })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Activity" }));
  await user.click(screen.getByText("View changes"));
  expect(screen.getByText("Record: site-a")).toBeTruthy();
  expect(screen.getByText("Request: request-site")).toBeTruthy();
  expect(screen.getByText("You")).toBeTruthy();
  expect(screen.getByText("null")).toBeTruthy();
  expect(screen.getByText(/"company_id": "company-a"/)).toBeTruthy();
});

test.each([true, false])(
  "logout clears private workspace with provider revocation=%s",
  async (providerRevoked) => {
    let signedIn = true;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) => {
        if (path === "/api/auth/logout") {
          signedIn = false;
          return response({
            authenticated: false,
            provider_revoked: providerRevoked,
          });
        }
        if (path === "/api/me")
          return signedIn
            ? response(identity)
            : response({ detail: "Sign in" }, 401);
        return response(workspace);
      }),
    );
    const user = userEvent.setup();
    const first = render(<App />);
    await screen.findByRole("heading", { name: "Workspace setup" });
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("heading", { name: "Sign in to Operis" });
    expect(screen.queryByText(identity.user.email)).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Organization" })).toBeNull();
    if (!providerRevoked)
      expect(screen.getByRole("alert").textContent).toContain(
        "remote session revocation could not be confirmed",
      );
    first.unmount();
    render(<App />);
    await screen.findByRole("heading", { name: "Sign in to Operis" });
  },
);

test("expired session on refresh clears tenant UI and explains reauthentication", async () => {
  let expired = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      path === "/api/me"
        ? response(identity)
        : expired
          ? response({ detail: "Expired" }, 401)
          : response(workspace),
    ),
  );
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("heading", { name: "Workspace setup" });
  expired = true;
  await user.click(screen.getByRole("button", { name: /Refresh/ }));
  await screen.findByRole("heading", { name: "Sign in to Operis" });
  expect(screen.getByRole("alert").textContent).toContain(
    "Your session has expired",
  );
  expect(screen.queryByRole("heading", { name: "Workspace setup" })).toBeNull();
});

test("expired code supports requesting a new link", async () => {
  let sends = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/auth/code") {
        sends++;
        return response({ message: "Check email" }, 202);
      }
      return response(
        { detail: "Your code or session is invalid or expired." },
        401,
      );
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.type(
    await screen.findByLabelText("Email address"),
    "admin@example.com",
  );
  await user.click(screen.getByRole("button", { name: /Send sign-in link/ }));
  await user.type(screen.getByLabelText("Sign-in code"), "123456");
  await user.click(screen.getByRole("button", { name: /Enter workspace/ }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "invalid or expired",
  );
  await user.click(
    screen.getByRole("button", {
      name: "Use another email or request a new link",
    }),
  );
  await user.click(screen.getByRole("button", { name: /Send sign-in link/ }));
  await screen.findByLabelText("Sign-in code");
  expect(sends).toBe(2);
});

test("saved write with failed refresh gives recovery without submitting twice", async () => {
  let writes = 0;
  let unavailable = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/me") return response(identity);
      if (path.endsWith("/companies")) {
        writes++;
        unavailable = true;
        return response({ id: "saved" }, 201);
      }
      return unavailable
        ? response({ detail: "Temporarily unavailable" }, 503)
        : response(workspace);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("heading", { name: "Workspace setup" });
  await user.click(screen.getByRole("button", { name: "Organization" }));
  await user.type(screen.getByLabelText("Company code"), "SAVED");
  await user.type(screen.getByLabelText("Company name"), "Saved company");
  await user.click(screen.getByRole("button", { name: "Add company" }));
  await screen.findByText(
    /Change saved, but the workspace could not be refreshed/,
  );
  expect(screen.queryByRole("button", { name: "Add company" })).toBeNull();
  unavailable = false;
  await user.click(screen.getByRole("button", { name: /Refresh/ }));
  await screen.findByRole("button", { name: "Add company" });
  expect(writes).toBe(1);
});
