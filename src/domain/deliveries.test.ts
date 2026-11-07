import { describe, expect, it } from "vitest";
import {
  MAX_STOPS,
  canAddStops,
  findDuplicateIds,
  normalizeAddress,
  sanitizeOcrResult,
  transition,
} from "./deliveries";

describe("límite de paradas", () => {
  it("el máximo es 30", () => expect(MAX_STOPS).toBe(30));
  it("permite llegar a 30 exactas", () => expect(canAddStops(28, 2)).toBe(true));
  it("rechaza la parada 31", () => expect(canAddStops(30, 1)).toBe(false));
});

describe("allowlist OCR", () => {
  it("conserva solo dirección, destinatario y unidad", () => {
    const r = sanitizeOcrResult({ address: " Calle 1 ", recipientName: "Demo", unitName: "U1" });
    expect(r.fields).toEqual({ address: "Calle 1", recipientName: "Demo", unitName: "U1" });
    expect(r.rejected).toEqual([]);
  });
  it("rechaza campos no permitidos como códigos o ids", () => {
    const r = sanitizeOcrResult({ address: "Calle 1", qr: "x", barcode: "y", trackingId: "z" });
    expect(r.rejected).toEqual(["qr", "barcode", "trackingId"]);
    expect(Object.keys(r.fields)).toEqual(["address", "recipientName", "unitName"]);
  });
  it("rechaza valores permitidos que no son texto", () => {
    expect(sanitizeOcrResult({ address: 123 }).rejected).toEqual(["address"]);
  });
});

describe("duplicados por dirección normalizada", () => {
  it("normaliza abreviaturas y tildes", () => {
    expect(normalizeAddress("Cra. 7 No. 45-10")).toBe(normalizeAddress("carrera 7 # 45 - 10"));
  });
  it("marca ambos registros duplicados", () => {
    const d = findDuplicateIds([
      { id: "a", address: "Cl 10 # 5-20" },
      { id: "b", address: "Calle 10 #5-20" },
      { id: "c", address: "Calle 11 # 5-20" },
    ]);
    expect([...d].sort()).toEqual(["a", "b"]);
  });
});

describe("transiciones de entrega", () => {
  it("pendiente -> completada", () => expect(transition("pending", "complete")).toBe("completed"));
  it("pendiente -> omitida -> pendiente", () =>
    expect(transition(transition("pending", "skip"), "restore")).toBe("pending"));
  it("eliminada no puede completarse", () =>
    expect(() => transition("removed", "complete")).toThrow());
  it("completada no puede omitirse", () =>
    expect(() => transition("completed", "skip")).toThrow());
});