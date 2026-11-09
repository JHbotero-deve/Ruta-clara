export interface AuthUser {
  id: string;
  email?: string;
  user_metadata?: { full_name?: string; company_name?: string };
}
export interface AuthSession {
  access_token: string;
  refresh_token: string;
  expires_at?: number;
  user: AuthUser;
}
const STORAGE_KEY = "ruta-clara-auth-v1";
const url = import.meta.env.VITE_SUPABASE_URL?.replace(/\/$/, "");
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
export const isSupabaseConfigured = Boolean(url && anonKey);
function endpoint(path: string) {
  if (!isSupabaseConfigured) throw new Error("Falta configurar VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY.");
  return url + "/auth/v1/" + path;
}
function headers(token?: string) {
  return { "Content-Type": "application/json", apikey: anonKey!, ...(token ? { Authorization: "Bearer " + token } : {}) };
}
async function parseResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.msg || data.message || data.error_description || data.error || "No fue posible completar la solicitud.");
  return data as T;
}
export function readSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) as AuthSession : null;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}
function saveSession(session: AuthSession | null) {
  if (typeof window === "undefined") return;
  if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  else localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event("ruta-clara-auth"));
}
async function refreshSession(session: AuthSession): Promise<AuthSession> {
  const response = await fetch(endpoint("token?grant_type=refresh_token"), {
    method: "POST", headers: headers(), body: JSON.stringify({ refresh_token: session.refresh_token }),
  });
  const data = await parseResponse<Omit<AuthSession, "expires_at"> & { expires_in?: number }>(response);
  const next = { ...data, expires_at: Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600) };
  saveSession(next);
  return next;
}
export async function getValidSession(): Promise<AuthSession | null> {
  const session = readSession();
  if (!session) return null;
  if (session.expires_at && session.expires_at > Math.floor(Date.now() / 1000) + 60) return session;
  try { return await refreshSession(session); }
  catch { saveSession(null); return null; }
}
export async function signIn(email: string, password: string): Promise<AuthSession> {
  const response = await fetch(endpoint("token?grant_type=password"), {
    method: "POST", headers: headers(), body: JSON.stringify({ email, password }),
  });
  const data = await parseResponse<Omit<AuthSession, "expires_at"> & { expires_in?: number }>(response);
  const session = { ...data, expires_at: Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600) };
  saveSession(session);
  return session;
}
export async function signUp(email: string, password: string, fullName: string, companyName: string): Promise<AuthSession | null> {
  const response = await fetch(endpoint("signup"), {
    method: "POST", headers: headers(),
    body: JSON.stringify({ email, password, data: { full_name: fullName, company_name: companyName } }),
  });
  const data = await parseResponse<Partial<AuthSession> & { user?: AuthUser; expires_in?: number }>(response);
  if (!data.access_token || !data.refresh_token || !data.user) return null;
  const session = { ...data, user: data.user, access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600) } as AuthSession;
  saveSession(session);
  return session;
}
export async function signOut() {
  const session = await getValidSession();
  if (session) await fetch(endpoint("logout"), { method: "POST", headers: headers(session.access_token) }).catch(() => undefined);
  saveSession(null);
}
export async function getCurrentUser(session: AuthSession): Promise<AuthUser> {
  const response = await fetch(endpoint("user"), { headers: headers(session.access_token) });
  return parseResponse<AuthUser>(response);
}
