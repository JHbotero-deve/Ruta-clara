// Puertos de infraestructura. NINGUNO está implementado: todos son "Próximamente".
// Las implementaciones reales requieren pruebas de seguridad previas (ver SECURITY.md).
import type { OcrFields } from "@/domain/deliveries";

export class NotImplementedError extends Error {
  constructor(feature: string) {
    super(`${feature}: Próximamente (no implementado en la demo)`);
  }
}

/** scanner: OCR local, solo sobre el recorte de la zona inferior autorizada.
 *  Prohibido: librerías QR/barcode, OCR remoto, persistir la imagen completa. */
export interface ScannerPort {
  extractFromAuthorizedCrop(crop: ImageBitmap): Promise<Partial<OcrFields>>;
}
export const scanner: ScannerPort = {
  async extractFromAuthorizedCrop() {
    throw new NotImplementedError("Escáner OCR local");
  },
};

/** address-validation: se ejecutará vía función de servidor (clave API solo en backend). */
export interface AddressValidationPort {
  validate(address: string): Promise<{ valid: boolean; normalized?: string }>;
}
export const addressValidation: AddressValidationPort = {
  async validate() {
    throw new NotImplementedError("Validación de direcciones");
  },
};

/** route-optimization: se ejecutará vía función de servidor. */
export interface RouteOptimizationPort {
  optimize(addresses: string[], origin: { lat: number; lng: number }): Promise<number[]>;
}
export const routeOptimization: RouteOptimizationPort = {
  async optimize() {
    throw new NotImplementedError("Optimización de ruta");
  },
};

/** persistence: sin base de datos todavía. */
export interface PersistencePort {
  saveRoute(data: unknown): Promise<void>;
}
export const persistence: PersistencePort = {
  async saveRoute() {
    throw new NotImplementedError("Persistencia");
  },
};