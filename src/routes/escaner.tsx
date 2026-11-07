import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Ban, Camera, Cpu, ImageUp, ScanLine } from "lucide-react";
import { AppShell, DemoBadge } from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ALLOWED_OCR_FIELDS } from "@/domain/deliveries";
import { pageHead } from "@/lib/seo";

export const Route = createFileRoute("/escaner")({
  head: pageHead("Escáner", "Guía de recorte para leer solo el texto autorizado de la etiqueta (demo, sin cámara)."),
  component: Scanner,
});

const FIELD_LABEL: Record<(typeof ALLOWED_OCR_FIELDS)[number], string> = {
  address: "Dirección",
  recipientName: "Cliente / destinatario",
  unitName: "Nombre de la unidad",
};

function Scanner() {
  // Solo simulación visual: no se pide cámara ni se ejecuta OCR.
  const [started, setStarted] = useState(false);

  return (
    <AppShell title="Escáner de etiquetas" subtitle="Simulación · cámara y OCR desactivados">
      <div className="scanner-frame relative aspect-[3/4] overflow-hidden rounded-xl md:aspect-video">
        <div className="absolute inset-x-4 top-4 bottom-[38%] flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-destructive/70 bg-destructive/25 text-center text-primary-foreground">
          <Ban className="h-6 w-6" />
          <p className="text-sm font-semibold">Zona excluida</p>
          <p className="max-w-56 text-xs opacity-80">QR, códigos de barras e identificadores no se leen</p>
        </div>
        <div className="absolute inset-x-4 bottom-4 h-[32%] rounded-md border-2 border-success bg-success/20 p-3 text-primary-foreground">
          <p className="text-sm font-semibold">Zona autorizada · texto inferior</p>
          <p className="text-xs opacity-80">Alinee aquí dirección, destinatario y unidad</p>
        </div>
        <div className="absolute right-3 top-3"><DemoBadge>Simulación</DemoBadge></div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge variant={started ? "success" : "muted"}>{started ? "Zona autorizada detectada (DEMO)" : "Zona autorizada: en espera"}</Badge>
        <Badge variant="secondary"><Cpu className="mr-1 h-3 w-3" />Lectura local (prevista)</Badge>
        <Badge variant="secondary"><Ban className="mr-1 h-3 w-3" />Códigos excluidos por diseño</Badge>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <Button size="lg" onClick={() => setStarted(true)}><ScanLine className="mr-2 h-4 w-4" />Iniciar escaneo (DEMO)</Button>
        <Button size="lg" variant="secondary" disabled><Camera className="mr-2 h-4 w-4" />Capturar · Próximamente</Button>
        <Button size="lg" variant="outline" disabled><ImageUp className="mr-2 h-4 w-4" />Importar · Próximamente</Button>
      </div>
      <p className="text-xs text-muted-foreground">
        En esta versión no se solicitan permisos de cámara. Cuando exista, el permiso solo se pedirá al pulsar “Iniciar escaneo”.
        Si la zona autorizada no se puede aislar, el proceso se detiene y se pide recaptura manual.
      </p>

      <div className="rounded-lg border bg-card p-4">
        <p className="mb-3 text-sm font-semibold">Campos autorizados</p>
        <ul className="space-y-2">
          {ALLOWED_OCR_FIELDS.map((f) => (
            <li key={f} className="flex items-center justify-between text-sm">
              <span>{FIELD_LABEL[f]}</span>
              <span className="font-mono text-xs text-muted-foreground">{started ? "texto DEMO" : "—"}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">Cualquier otro campo se rechaza. No se infieren identificadores.</p>
      </div>
    </AppShell>
  );
}