import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, ScanLine } from "lucide-react";
import { AppShell, Stat } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { MAX_STOPS, findDuplicateIds } from "@/domain/deliveries";
import { pageHead } from "@/lib/seo";
import { useDemoStops } from "@/state/demo-store";

export const Route = createFileRoute("/")({
  head: pageHead("Inicio", "Resumen de entregas del día en Ruta Clara (datos DEMO)."),
  component: Index,
});

function Index() {
  const stops = useDemoStops().filter((s) => s.state !== "removed");
  const dups = findDuplicateIds(stops);
  const alerts = stops.filter((s) => dups.has(s.id) || s.ambiguous || !s.unitName).length;
  const done = stops.filter((s) => s.state === "completed").length;

  return (
    <AppShell title="Resumen del día" subtitle="Ruta DEMO · sin datos reales">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Entregas totales" value={stops.length} />
        <Stat label="Pendientes" value={stops.filter((s) => s.state === "pending").length} />
        <Stat label="Completadas" value={done} tone="success" />
        <Stat label="Alertas" value={alerts} tone="warning" />
      </div>

      <div className="rounded-lg border bg-card p-4">
        <div className="mb-2 flex justify-between text-sm">
          <span className="font-medium">Límite de paradas</span>
          <span className="font-mono">{stops.length} / {MAX_STOPS}</span>
        </div>
        <Progress value={(stops.length / MAX_STOPS) * 100} />
        <p className="mt-2 text-xs text-muted-foreground">Máximo {MAX_STOPS} paradas por ruta.</p>
      </div>

      <Button asChild size="lg" className="h-14 w-full text-base">
        <Link to="/escaner"><ScanLine className="mr-2 h-5 w-5" /> Escanear etiquetas</Link>
      </Button>

      {alerts > 0 && (
        <Link to="/revision" className="flex items-center gap-3 rounded-lg border border-warning/40 bg-warning-soft p-3 text-sm text-warning-foreground">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {alerts} entregas requieren revisión (duplicadas, ambiguas o incompletas).
        </Link>
      )}
    </AppShell>
  );
}