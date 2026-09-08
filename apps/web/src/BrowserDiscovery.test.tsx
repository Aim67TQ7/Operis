import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserDiscovery } from "./BrowserDiscovery";
const response = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const preview = {
  receipt: {
    payload: {
      summary: {
        measurements: [
          { key: "baqs", status: "forbidden", count: null, counts: null },
        ],
      },
      expires_at: 9999999999,
    },
    signature: "signed",
  },
  report: { coverage: { measured: 0, attempted: 11 }, limitations: [] },
};
const props = {
  prefix: "/tenants/a",
  companyId: "company-a",
  onSaved: vi.fn(async () => {}),
  onExpired: vi.fn(),
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});
async function credentials() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Set up browser scan" }));
  await user.type(await screen.findByLabelText("Epicor username"), "test-user");
  await user.type(screen.getByLabelText("Epicor password"), "private-password");
  await user.type(screen.getByLabelText("Epicor API key"), "private-api-key");
  expect(
    (
      screen.getByRole("button", {
        name: "Run read-only discovery",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  await user.click(screen.getByRole("checkbox"));
  await user.click(
    screen.getByRole("button", { name: "Run read-only discovery" }),
  );
  return user;
}
test("scan previews unknowns before explicit save; credentials never enter receipt or storage", async () => {
  const requests: { path: string; options: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options: RequestInit) => {
      requests.push({ path, options });
      return response(
        path.endsWith("/run")
          ? preview
          : path.endsWith("/save")
            ? { id: "saved-a" }
            : { endpoint: "https://erp.example/Test" },
      );
    }),
  );
  render(<BrowserDiscovery {...props} />);
  const user = await credentials();
  await screen.findByRole("region", { name: "Discovery preview" });
  expect(screen.getByText("Unknown")).toBeTruthy();
  expect(requests.filter((r) => r.path.endsWith("/save"))).toHaveLength(0);
  const scan = requests.find((r) => r.path.endsWith("/run"))!;
  expect(JSON.parse(scan.options.body as string)).toEqual({
    username: "test-user",
    password: "private-password",
    api_key: "private-api-key",
  });
  expect(scan.options.credentials).toBe("same-origin");
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
  await user.click(screen.getByRole("button", { name: "Save assessment" }));
  await waitFor(() => expect(props.onSaved).toHaveBeenCalledWith("saved-a"));
  expect(requests.find((r) => r.path.endsWith("/save"))!.options.body).toBe(
    JSON.stringify(preview.receipt),
  );
  await user.click(screen.getByRole("button", { name: "Start another scan" }));
  expect(
    (screen.getByLabelText("Epicor password") as HTMLInputElement).value,
  ).toBe("");
  expect(
    (screen.getByLabelText("Epicor API key") as HTMLInputElement).value,
  ).toBe("");
});
test("cancel clears credentials and ignores a late result", async () => {
  let complete: (value: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string) =>
      path.endsWith("/run")
        ? new Promise<Response>((resolve) => {
            complete = resolve;
          })
        : Promise.resolve(response({ endpoint: "https://erp.example/Test" })),
    ),
  );
  render(<BrowserDiscovery {...props} />);
  const user = await credentials();
  expect(
    (screen.getByLabelText("Epicor password") as HTMLInputElement).value,
  ).toBe("");
  await user.click(screen.getByRole("button", { name: "Cancel scan" }));
  await act(async () => complete(response(preview)));
  expect(
    screen.queryByRole("region", { name: "Discovery preview" }),
  ).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain(
    "No assessment was saved",
  );
});
test("changing company aborts in-flight scan and discards credentials/results", async () => {
  let signal: AbortSignal | undefined;
  let complete: (value: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, options: RequestInit) => {
      if (path.endsWith("/run")) {
        signal = options.signal as AbortSignal;
        return new Promise<Response>((resolve) => {
          complete = resolve;
        });
      }
      return Promise.resolve(
        response({ endpoint: "https://erp.example/Test" }),
      );
    }),
  );
  const view = render(<BrowserDiscovery key="a" {...props} />);
  await credentials();
  view.rerender(<BrowserDiscovery key="b" {...props} companyId="company-b" />);
  expect(signal?.aborted).toBe(true);
  await act(async () => complete(response(preview)));
  expect(
    screen.queryByRole("region", { name: "Discovery preview" }),
  ).toBeNull();
  expect(screen.queryByLabelText("Epicor password")).toBeNull();
});
test("save failure preserves the same receipt for a safe retry", async () => {
  let attempts = 0;
  const receipts: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options: RequestInit) => {
      if (path.endsWith("/save")) {
        receipts.push(options.body);
        return ++attempts === 1
          ? response({ detail: "Temporary failure" }, 503)
          : response({ id: "saved-a" });
      }
      return response(
        path.endsWith("/run")
          ? preview
          : { endpoint: "https://erp.example/Test" },
      );
    }),
  );
  render(<BrowserDiscovery {...props} />);
  const user = await credentials();
  await user.click(
    await screen.findByRole("button", { name: "Save assessment" }),
  );
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Temporary failure",
  );
  await user.click(screen.getByRole("button", { name: "Save assessment" }));
  await waitFor(() => expect(props.onSaved).toHaveBeenCalled());
  expect(receipts).toEqual([
    JSON.stringify(preview.receipt),
    JSON.stringify(preview.receipt),
  ]);
});
test("expired session sends the user back to sign-in", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response({ detail: "Session expired" }, 401)),
  );
  render(<BrowserDiscovery {...props} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Set up browser scan" }),
  );
  await waitFor(() => expect(props.onExpired).toHaveBeenCalled());
  expect(screen.queryByLabelText("Epicor password")).toBeNull();
});
