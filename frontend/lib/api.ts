const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 12000;

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("prep-session");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.token ?? null;
  } catch {
    return null;
  }
}

function handleUnauthorized() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("prep-session");
  localStorage.removeItem("perp-session");
  window.location.href = "/login";
}

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;
  errorType?: string;
  reason?: string;
  suggestions: string[];

  constructor(
    message: string,
    code: string,
    status: number,
    details: Record<string, unknown> = {},
    errorType?: string,
    reason?: string,
    suggestions: string[] = [],
  ) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
    this.errorType = errorType;
    this.reason = reason;
    this.suggestions = suggestions;
  }
}

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  const token = getToken();

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === "AbortError") {
      throw new ApiError("The API took too long to respond.", "REQUEST_TIMEOUT", 408);
    }
    throw new ApiError("Network error.", "NETWORK_ERROR", 0);
  } finally {
    clearTimeout(timeoutId);
  }

  // 🔥 AUTO LOGOUT ON 401
  if (response.status === 401) {
    handleUnauthorized();
    throw new ApiError("Session expired. Please login again.", "UNAUTHORIZED", 401);
  }

  let payload: any = null;

  try {
    payload = await response.json();
  } catch {
    throw new ApiError("Invalid API response.", "INVALID_RESPONSE", response.status);
  }

  if (!response.ok || !payload?.ok || !payload?.data) {
    throw new ApiError(
      payload?.error?.message ?? "Request failed.",
      payload?.error?.code ?? "UNKNOWN_ERROR",
      response.status,
      payload?.error?.details ?? {},
      payload?.error?.error_type,
      payload?.error?.reason,
      payload?.error?.suggestions ?? [],
    );
  }

  return payload.data;
}