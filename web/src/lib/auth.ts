const API_BASE_URL =
  process.env.NEXT_PUBLIC_COMPANION_API_URL ?? "http://127.0.0.1:8000";

const AUTH_TOKEN_KEY = "family-companion-auth-token";
const AUTH_USER_KEY = "family-companion-auth-user";

export type AuthUser = {
  id: string;
  phone: string;
  nickname?: string;
};

export type VerifyLoginCodeResponse = {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
};

export function getAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function getAuthUser(): AuthUser | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(AUTH_USER_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setAuthSession(result: VerifyLoginCodeResponse): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_KEY, result.access_token);
  window.localStorage.setItem(AUTH_USER_KEY, JSON.stringify(result.user));
}

export function clearAuthToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_USER_KEY);
}

async function requestAuthJson<T>(path: string, payload: Record<string, string>): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const bodyText = await response.text();
    let detail = bodyText;
    try {
      const parsed = JSON.parse(bodyText) as { detail?: unknown };
      detail = typeof parsed.detail === "string" ? parsed.detail : bodyText;
    } catch {
      detail = bodyText;
    }
    throw new Error(detail || `Backend request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function sendLoginCode(phone: string): Promise<{ ok: boolean; expires_in_seconds: number; test_mode: boolean }> {
  return requestAuthJson("/api/auth/send-code", { phone });
}

export async function verifyLoginCode(phone: string, code: string): Promise<VerifyLoginCodeResponse> {
  const result = await requestAuthJson<VerifyLoginCodeResponse>("/api/auth/verify", { phone, code });
  setAuthSession(result);
  return result;
}
