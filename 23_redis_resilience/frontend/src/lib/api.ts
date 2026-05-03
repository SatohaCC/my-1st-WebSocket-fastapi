const HTTP_URL = process.env.NEXT_PUBLIC_HTTP_URL ?? "http://localhost:8000";

export async function loginApi(username: string, password: string) {
  const res = await fetch(`${HTTP_URL}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return { res, data: (await res.json()) as unknown };
}

export async function fetchMeApi(token: string | null) {
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(`${HTTP_URL}/me`, { headers });
  return { res, data: (await res.json()) as unknown };
}
