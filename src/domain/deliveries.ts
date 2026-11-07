// Reglas de dominio puras. Sin React, sin red, sin almacenamiento.

export const MAX_STOPS = 30;

/** Únicos campos que el OCR puede producir. Cualquier otro se rechaza. */
export const ALLOWED_OCR_FIELDS = ["address", "recipientName", "unitName"] as const;
export type AllowedOcrField = (typeof ALLOWED_OCR_FIELDS)[number];
export type OcrFields = Record<AllowedOcrField, string>;

export interface SanitizeResult {
  fields: OcrFields;
  rejected: string[];
}

/** Conserva solo campos permitidos de tipo string; lista los rechazados. */
export function sanitizeOcrResult(raw: Record<string, unknown>): SanitizeResult {
  const fields: OcrFields = { address: "", recipientName: "", unitName: "" };
  const rejected: string[] = [];
  for (const [key, value] of Object.entries(raw)) {
    if ((ALLOWED_OCR_FIELDS as readonly string[]).includes(key) && typeof value === "string") {
      fields[key as AllowedOcrField] = value.trim();
    } else {
      rejected.push(key);
    }
  }
  return { fields, rejected };
}

export function canAddStops(current: number, adding: number): boolean {
  return adding >= 0 && current + adding <= MAX_STOPS;
}

export function normalizeAddress(address: string): string {
  return address
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\bno\.?\s*/g, "# ")
    .replace(/\b(cl|cll|calle)\b\.?/g, "calle")
    .replace(/\b(cra|kr|kra|carrera)\b\.?/g, "carrera")
    .replace(/[^a-z0-9#\s-]/g, " ")
    .replace(/\s*#\s*/g, " # ")
    .replace(/\s*-\s*/g, "-")
    .replace(/\s+/g, " ")
    .trim();
}

/** Devuelve los ids que comparten dirección normalizada con otro registro. */
export function findDuplicateIds(items: { id: string; address: string }[]): Set<string> {
  const groups = new Map<string, string[]>();
  for (const it of items) {
    const key = normalizeAddress(it.address);
    if (!key) continue;
    groups.set(key, [...(groups.get(key) ?? []), it.id]);
  }
  const dup = new Set<string>();
  for (const ids of groups.values()) if (ids.length > 1) ids.forEach((id) => dup.add(id));
  return dup;
}

export type ReviewStatus = "ok" | "duplicate" | "ambiguous" | "incomplete";

export function reviewStatus(f: OcrFields, isDuplicate: boolean, ambiguous = false): ReviewStatus {
  if (!f.address || !f.recipientName || !f.unitName) return "incomplete";
  if (isDuplicate) return "duplicate";
  if (ambiguous) return "ambiguous";
  return "ok";
}

export type DeliveryState = "pending" | "completed" | "skipped" | "removed";
export type DeliveryAction = "complete" | "skip" | "restore" | "remove";

const TRANSITIONS: Record<DeliveryState, Partial<Record<DeliveryAction, DeliveryState>>> = {
  pending: { complete: "completed", skip: "skipped", remove: "removed" },
  skipped: { restore: "pending", complete: "completed", remove: "removed" },
  completed: { restore: "pending" },
  removed: {},
};

export function transition(state: DeliveryState, action: DeliveryAction): DeliveryState {
  const next = TRANSITIONS[state][action];
  if (!next) throw new Error(`Transición inválida: ${state} -> ${action}`);
  return next;
}

export function canTransition(state: DeliveryState, action: DeliveryAction): boolean {
  return TRANSITIONS[state][action] !== undefined;
}