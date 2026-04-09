import "server-only";

export function getBackendBaseUrl() {
  return (
    process.env.BACKEND_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    process.env.NEXT_PUBLIC_BACKEND_URL ??
    "http://localhost:8000"
  );
}

export function getInternalBackendHeaders(init?: HeadersInit) {
  const headers = new Headers(init);
  const internalApiKey = process.env.INTERNAL_API_KEY;

  if (!internalApiKey && process.env.NODE_ENV === "production") {
    throw new Error("INTERNAL_API_KEY is not configured.");
  }

  if (internalApiKey) {
    headers.set("X-Internal-Api-Key", internalApiKey);
  }

  return headers;
}
