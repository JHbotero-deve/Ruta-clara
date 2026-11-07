import { createFileRoute } from "@tanstack/react-router";
import { ArrowDown, ArrowUp, Navigation } from "lucide-react";
import { AppShell, DemoBadge, Stat } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { pageHead } from "@/lib/seo";
import { demoStore, useDemoStops } from "@/state/demo-store";

export const Route = createFileRoute("/ruta")({
  head: pageHead("Ruta", "Mapa y orden de paradas de ejemplo (DEMO, sin optimización real)."),
  component: RoutePage,
});

const PINS: [number, number][] = [[18, 70], [30, 40], [48, 58], [60, 25], [72, 62], [84, 38], [40, 82]];

function RoutePage() {
  const stops = useDemoStops().filter((s) => s.state !== "removed");
  return (
    <AppShell title="Ruta" subtitle="Orden manual · optimización: Próximamente">
      <div className="map-grid relative aspect-video overflow-hidden rounded-xl border">
        {stops.map((s, i) => {
          const [x, y] = PINS[i % PINS.length]!;
          return (
            <span key={s.id} style={{ left: `${x}%`, top: `${y}%` }}
              className={`absolute flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full font-mono text-xs font-semibold shadow ${s.state === "completed" ? "bg-success text-primary-foreground" : "bg-primary text-primary-foreground"}`}>
              {i + 1}
            </span>
          );
        })}
        <div className="absolute left-3 top-3"><DemoBadge>Mapa de ejemplo · no real</DemoBadge></div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="Distancia (DEMO)" value="—" />
        <Stat label="Tiempo (DEMO)" value="—" />
      </div>

      <ol className="space-y-2">
        {stops.map((s, i) => (
          <li key={s.id} className="flex items-center gap-3 rounded-lg border bg-card p-3">
            <span className="font-mono text-sm text-muted-foreground">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{s.address}</p>
              <p className="truncate text-xs text-muted-foreground">{s.recipientName} · {s.unitName || "Sin unidad"}</p>
            </div>
            <Button size="icon" variant="ghost" aria-label="Subir" disabled={i === 0} onClick={() => demoStore.move(s.id, -1)}><ArrowUp className="h-4 w-4" /></Button>
            <Button size="icon" variant="ghost" aria-label="Bajar" disabled={i === stops.length - 1} onClick={() => demoStore.move(s.id, 1)}><ArrowDown className="h-4 w-4" /></Button>
          </li>
        ))}
      </ol>

      <Button size="lg" className="w-full" disabled><Navigation className="mr-2 h-4 w-4" />Navegación externa · deshabilitada en demo</Button>
    </AppShell>
  );
}