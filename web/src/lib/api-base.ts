const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_COMPANION_API_URL;
  const value = raw == null ? DEFAULT_API_BASE_URL : raw.trim();
  const trimmed = value.replace(/\/+$/, "");

  if (trimmed === "/api") {
    return "";
  }
  if (trimmed.endsWith("/api")) {
    return trimmed.slice(0, -4);
  }
  return trimmed;
}
