"use client";
// All calls go to the on-premise API. No other host is ever contacted.
export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const KEY = "vayu_token";

export const getToken = () => (typeof window === "undefined" ? null : sessionStorage.getItem(KEY));
export const setToken = (t: string) => sessionStorage.setItem(KEY, t);
export const clearToken = () => sessionStorage.removeItem(KEY);

export async function api<T = any>(path: string, opts: { method?: string; body?: any; token?: string; form?: FormData } = {}): Promise<T> {
  const token = opts.token ?? getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(API + path, {
      method: opts.method || (opts.body !== undefined || opts.form ? "POST" : "GET"),
      headers,
      body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
    });
  } catch {
    throw new Error("Cannot reach the VAYU-READY server. Check that the API is running.");
  }
  if (res.status === 401 && !opts.token && !path.startsWith("/auth/")) {
    clearToken();
    if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) location.href = "/login?expired=1";
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.");
  return data as T;
}

export async function download(path: string, filename: string) {
  const res = await fetch(API + path, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error("The report could not be created.");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const wsUrl = () => API.replace(/^http/, "ws") + "/ws/live?token=" + encodeURIComponent(getToken() || "");

export function fmtTime(iso?: string | null) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
}

export function fmtDate(iso?: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}
