// Estado en memoria solo para la demo visual. No persiste nada.
import { useSyncExternalStore } from "react";
import { transition, type DeliveryAction, type DeliveryState, type OcrFields } from "@/domain/deliveries";

export interface DemoStop extends OcrFields {
  id: string;
  state: DeliveryState;
  ambiguous?: boolean;
}

const seed: DemoStop[] = [
  { id: "d1", recipientName: "Cliente DEMO 01", unitName: "Conjunto DEMO Alfa", address: "Calle 10 # 5-20, Bogotá", state: "completed" },
  { id: "d2", recipientName: "Cliente DEMO 02", unitName: "Torre DEMO Beta", address: "Carrera 7 # 45-10, Bogotá", state: "completed" },
  { id: "d3", recipientName: "Cliente DEMO 03", unitName: "Edificio DEMO Gamma", address: "Calle 72 # 11-30, Bogotá", state: "pending" },
  { id: "d4", recipientName: "Cliente DEMO 04", unitName: "Conjunto DEMO Delta", address: "Cl 10 # 5-20, Bogotá", state: "pending" },
  { id: "d5", recipientName: "Cliente DEMO 05", unitName: "", address: "Av. Calle 26 # 68-35, Bogotá", state: "pending" },
  { id: "d6", recipientName: "Cliente DEMO 06", unitName: "Unidad DEMO Épsilon", address: "Calle 80 sur, Bogotá", state: "pending", ambiguous: true },
  { id: "d7", recipientName: "Cliente DEMO 07", unitName: "Torre DEMO Zeta", address: "Carrera 15 # 93-60, Bogotá", state: "skipped" },
];

let stops = seed;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const demoStore = {
  subscribe(l: () => void) {
    listeners.add(l);
    return () => listeners.delete(l);
  },
  get: () => stops,
  update(id: string, patch: Partial<OcrFields>) {
    stops = stops.map((s) => (s.id === id ? { ...s, ...patch } : s));
    emit();
  },
  act(id: string, action: DeliveryAction) {
    stops = stops.map((s) => (s.id === id ? { ...s, state: transition(s.state, action) } : s));
    emit();
  },
  move(id: string, dir: -1 | 1) {
    const i = stops.findIndex((s) => s.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= stops.length) return;
    const next = [...stops];
    [next[i], next[j]] = [next[j]!, next[i]!];
    stops = next;
    emit();
  },
};

export function useDemoStops() {
  return useSyncExternalStore(demoStore.subscribe, demoStore.get, () => seed);
}