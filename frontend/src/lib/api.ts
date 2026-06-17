// Thin fetch wrapper. Auth is cookie-based, so every request includes credentials.
//
// The short-lived access cookie is transparently renewed: on a 401 we hit
// /api/auth/refresh once (coalesced across concurrent calls) and retry the
// original request, so an expired access token mid-session doesn't surface as
// "not authenticated" while the 30-day refresh cookie is still valid.

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Auth endpoints that must NOT trigger a refresh-and-retry (avoids loops and
// retrying genuine credential failures). /api/auth/me is intentionally absent —
// a 401 there should still try to renew via the refresh cookie.
const NO_REFRESH = ["/api/auth/refresh", "/api/auth/login", "/api/auth/register", "/api/auth/logout"];

let refreshInFlight: Promise<boolean> | null = null;

function tryRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch("/api/auth/refresh", { method: "POST", credentials: "include" })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function request<T>(method: string, path: string, body?: unknown, allowRetry = true): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && allowRetry && !NO_REFRESH.some((p) => path.startsWith(p))) {
    if (await tryRefresh()) {
      return request<T>(method, path, body, false); // retry once with a fresh access token
    }
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail)
        : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};
