import { useEffect, useSyncExternalStore } from "react";
import { transition, type DeliveryAction, type DeliveryState, type OcrFields } from "@/domain/deliveries";
import { listDeliveries, reorderDeliveries, transitionDelivery, updateDelivery, type DeliveryRecord } from "@/lib/supabase-data";
export interface DemoStop extends OcrFields {
  id: string;
  state: DeliveryState;
  ambiguous?: boolean;
  assigned_to?: string | null;
}
let stops: DemoStop[] = [];
let loading = false;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach(listener => listener());
function mapRecord(row: DeliveryRecord): DemoStop {
  return { id: row.id, address: row.address, recipientName: row.recipient_name, unitName: row.unit_name, state: row.status, assigned_to: row.assigned_to };
}
async function load() {
  if (loading) return;
  loading = true;
  try { stops = (await listDeliveries()).map(mapRecord); }
  finally { loading = false; emit(); }
}
export const demoStore = {
  subscribe(listener: () => void) { listeners.add(listener); return () => listeners.delete(listener); },
  get: () => stops,
  async update(id: string, patch: Partial<OcrFields>) {
    const updated = await updateDelivery(id, patch);
    if (updated) stops = stops.map(stop => stop.id === id ? mapRecord(updated) : stop);
    emit();
  },
  async act(id: string, action: DeliveryAction) {
    const current = stops.find(stop => stop.id === id);
    if (!current) return;
    transition(current.state, action);
    const updated = await transitionDelivery(id, action, current.state);
    if (updated) stops = stops.map(stop => stop.id === id ? mapRecord(updated) : stop);
    emit();
  },
  async move(id: string, direction: -1 | 1) {
    const index = stops.findIndex(stop => stop.id === id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= stops.length) return;
    const next = [...stops];
    [next[index], next[target]] = [next[target]!, next[index]!];
    stops = next;
    emit();
    await reorderDeliveries(stops.map(stop => stop.id));
  },
};
export function useDemoStops() {
  const value = useSyncExternalStore(demoStore.subscribe, demoStore.get, () => []);
  useEffect(() => { void load().catch(error => console.error("No se pudieron cargar las entregas:", error)); }, []);
  return value;
}
