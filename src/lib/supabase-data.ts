import { getValidSession } from "@/lib/supabase-auth";
import type { DeliveryAction, DeliveryState, OcrFields } from "@/domain/deliveries";
const baseUrl = import.meta.env.VITE_SUPABASE_URL?.replace(/\/$/, "");
const apiKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
export interface DeliveryRecord {
  id: string;
  organization_id: string;
  assigned_to: string | null;
  recipient_name: string;
  unit_name: string;
  address: string;
  status: DeliveryState;
  sort_order: number;
}
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = await getValidSession();
  if (!session) throw new Error("La sesión expiró. Inicia sesión nuevamente.");
  const response = await fetch(baseUrl + "/rest/v1/" + path, {
    ...init,
    headers: { apikey: apiKey!, Authorization: "Bearer " + session.access_token, "Content-Type": "application/json", ...(init.headers || {}) },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.message || body?.hint || "No fue posible consultar la base de datos.");
  return body as T;
}
export async function getMyMembership() {
  const session = await getValidSession();
  if (!session) throw new Error("No hay una sesión activa.");
  const profiles = await request<{ organization_id: string }[]>("profiles?select=organization_id&id=eq." + session.user.id);
  if (!profiles[0]) throw new Error("El usuario no tiene una empresa asignada.");
  const memberships = await request<{ role: "owner" | "admin" | "driver" }[]>("memberships?select=role&organization_id=eq." + profiles[0].organization_id + "&user_id=eq." + session.user.id);
  if (!memberships[0]) throw new Error("No existe una membresía activa para esta empresa.");
  return { organizationId: profiles[0].organization_id, role: memberships[0].role, userId: session.user.id };
}
export async function listDeliveries(): Promise<DeliveryRecord[]> {
  return request<DeliveryRecord[]>("deliveries?select=*&order=sort_order.asc,created_at.asc");
}
export async function createDelivery(fields: OcrFields, assignedTo?: string) {
  const membership = await getMyMembership();
  if (membership.role === "driver") throw new Error("Solo un administrador puede crear entregas.");
  const current = await listDeliveries();
  const rows = await request<DeliveryRecord[]>("deliveries?select=*", {
    method: "POST", headers: { Prefer: "return=representation" },
    body: JSON.stringify({ recipient_name: fields.recipientName, unit_name: fields.unitName, address: fields.address, organization_id: membership.organizationId, created_by: membership.userId, assigned_to: assignedTo || null, sort_order: current.length }),
  });
  return rows[0];
}
export async function updateDelivery(id: string, fields: Partial<OcrFields>) {
  const body = { ...(fields.address !== undefined ? { address: fields.address } : {}), ...(fields.recipientName !== undefined ? { recipient_name: fields.recipientName } : {}), ...(fields.unitName !== undefined ? { unit_name: fields.unitName } : {}) };
  const rows = await request<DeliveryRecord[]>("deliveries?id=eq." + id + "&select=*", {
    method: "PATCH", headers: { Prefer: "return=representation" }, body: JSON.stringify(body),
  });
  return rows[0];
}
export async function transitionDelivery(id: string, action: DeliveryAction, current: DeliveryState) {
  const next: Record<DeliveryAction, DeliveryState> = { complete: "completed", skip: "skipped", restore: "pending", remove: "removed" };
  const membership = await getMyMembership();
  if (membership.role === "driver") {
    return request<DeliveryRecord>("rpc/update_assigned_delivery_status", { method: "POST", body: JSON.stringify({ delivery_id: id, new_status: next[action] }) });
  }
  const rows = await request<DeliveryRecord[]>("deliveries?id=eq." + id + "&select=*", {
    method: "PATCH", headers: { Prefer: "return=representation" },
    body: JSON.stringify({ status: next[action], completed_at: next[action] === "completed" ? new Date().toISOString() : null }),
  });
  return rows[0];
}
export async function reorderDeliveries(ids: string[]) {
  await Promise.all(ids.map((id, index) => request("deliveries?id=eq." + id, { method: "PATCH", body: JSON.stringify({ sort_order: index }) })));
}

export async function listTeamMembers() {
  const membership = await getMyMembership();
  const [profiles, memberships] = await Promise.all([
    request<{ id: string; full_name: string; email: string }[]>("profiles?select=id,full_name,email&organization_id=eq." + membership.organizationId),
    request<{ user_id: string; role: "owner" | "admin" | "driver" }[]>("memberships?select=user_id,role&organization_id=eq." + membership.organizationId),
  ]);
  return memberships.map(member => ({ ...member, ...profiles.find(profile => profile.id === member.user_id) }));
}
export async function createTeamInvite(role: "admin" | "driver") {
  return request<string>("rpc/create_organization_invite", { method: "POST", body: JSON.stringify({ target_role: role }) });
}
