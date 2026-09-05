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
