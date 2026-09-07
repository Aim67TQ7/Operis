export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...options.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      0,
      "Operis could not be reached. Check your connection and try again.",
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "The request could not be completed.";
    throw new ApiError(
      response.status,
      `${message} Reference: ${response.headers.get("X-Request-ID") || "unavailable"}`,
    );
  }
  if (data === null)
    throw new ApiError(502, "The server returned an unexpected response.");
  return data as T;
}

export type Tenant = {
  id: string;
  name: string;
  role: "admin" | "operator" | "viewer";
};
export type Identity = {
  user: { id: string; email: string };
  tenants: Tenant[];
};
export type Company = { id: string; code: string; name: string };
export type Site = Company & { company_id: string };
export type AuditEvent = {
  id: string;
  actor_id: string | null;
  action: string;
  table_name: string;
  record_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
  request_id: string | null;
};
export type Workspace = {
  role: Tenant["role"];
  companies: Company[];
  sites: Site[];
  memberships: { user_id: string; role: string }[];
  audit_events: AuditEvent[];
};
