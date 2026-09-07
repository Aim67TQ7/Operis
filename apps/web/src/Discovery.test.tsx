import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Discovery } from "./Discovery";
import type { Tenant } from "./api";
const tenant: Tenant = {
  id: "tenant-a",
  name: "Synthetic organization",
  role: "admin",
};
const company = { id: "company-a", name: "Synthetic company", code: "TEST" };
const run = {
  id: "run-a",
  company_id: company.id,
  created_at: "2026-09-07T10:00:00Z",
  status: "complete",
  scanner_version: "0.3.0",
  package_sha256: "a".repeat(64),
  summary: {
    measurements: [
      { key: "ap_invoices", status: "forbidden", count: null, counts: null },
    ],
  },
  self_evaluation: {
    coverage: { measured: 0, attempted: 11 },
    findings: [],
    recommendations: [],
    limitations: ["Customer validation required."],
  },
  pilot_request: null,
};
const response = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
test("upload sends reviewed ZIP through same-origin API and persists pilot request", async () => {
  const requests: { path: string; options: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options: RequestInit) => {
      requests.push({ path, options });
      if (path.endsWith("/pilot"))
        return response({ id: "pilot-a", status: "requested" });
      if (path.endsWith("/run-a")) return response(run);
      if (options.method === "POST")
        return response({ id: "run-a", duplicate: false });
      return response([]);
    }),
  );
  const user = userEvent.setup();
  render(
    <Discovery
      tenant={tenant}
      companies={[company]}
      onExpired={vi.fn()}
      onSetup={vi.fn()}
    />,
  );
  await screen.findByText(
    "No assessments yet. Upload your first completed scan above.",
  );
  const upload = screen.getByRole("button", {
    name: "Upload and create assessment",
  });
  expect((upload as HTMLButtonElement).disabled).toBe(true);
  const file = new File(["test archive bytes"], "results.zip", {
    type: "application/zip",
  });
  await user.upload(screen.getByLabelText("Discovery results ZIP"), file);
  expect((upload as HTMLButtonElement).disabled).toBe(true);
  await user.click(screen.getByRole("checkbox"));
  await user.click(upload);
  await screen.findByRole("region", { name: "Saved assessment" });
  expect(screen.getByText("Unknown")).toBeTruthy();
  expect(screen.getByText(/Coverage is not a health score/)).toBeTruthy();
  const request = requests.find((r) => r.options.method === "POST")!;
  expect(request.path).toBe(
    "/api/tenants/tenant-a/companies/company-a/discovery",
  );
  expect(request.options.body).toBe(file);
  expect(request.options.credentials).toBe("same-origin");
  expect(request.options.headers).toEqual({
    "Content-Type": "application/zip",
  });
  await user.click(
    screen.getByRole("button", { name: "Request pilot review" }),
  );
  await screen.findByText(/Pilot request saved · requested/);
  expect(
    screen.queryByRole("button", { name: "Request pilot review" }),
  ).toBeNull();
});
test("viewer sees history but no upload, configuration or pilot controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      response(path.endsWith("/run-a") ? run : [run]),
    ),
  );
  render(
    <Discovery
      tenant={{ ...tenant, role: "viewer" }}
      companies={[company]}
      onExpired={vi.fn()}
      onSetup={vi.fn()}
    />,
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "View assessment" }),
  );
  await screen.findByRole("region", { name: "Saved assessment" });
  expect(screen.queryByLabelText("Discovery results ZIP")).toBeNull();
  expect(
    screen.queryByRole("link", { name: "Download company configuration" }),
  ).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Request pilot review" }),
  ).toBeNull();
});
test("expired session returns to sign-in and never claims an empty successful history", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response({ detail: "Session expired" }, 401)),
  );
  const expire = vi.fn();
  render(
    <Discovery
      tenant={tenant}
      companies={[company]}
      onExpired={expire}
      onSetup={vi.fn()}
    />,
  );
  await waitFor(() => expect(expire).toHaveBeenCalled());
  expect(screen.getByRole("alert").textContent).toContain("Session expired");
});
