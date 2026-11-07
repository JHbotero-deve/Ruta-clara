import { createFileRoute } from "@tanstack/react-router";
import { Check, LocateFixed, RotateCcw, SkipForward, Trash2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { canTransition, type DeliveryState } from "@/domain/deliveries";
import { pageHead } from "@/lib/seo";
import { demoStore, useDemoStops } from "@/state/demo-store";

export const Route = createFileRoute("/entregas")({
  head: pageHead("Entregas", "Marque entregas completadas, omita o elimine paradas (DEMO)."),
  component: Deliveries,
});

const STATE: Record<DeliveryState, { label: string; variant: "success" | "muted" | "warning" | "danger" }> = {
  pending: { label: "Pendiente", variant: "muted" },
  completed: { label: "Completada", variant: "success" },
  skipped: { label: "Omitida", variant: "warning" },
  removed: { label: "Eliminada", variant: "danger" },
};

function Deliveries() {
  const stops = useDemoStops().filter((s) => s.state !== "removed");
  const done = stops.filter((s) => s.state === "completed").length;
  const next = stops.find((s) => s.state === "pending");

  return (
    <AppShell title="Entregas" subtitle={`${done} de ${stops.length} completadas`}>
      <Progress value={stops.length ? (done / stops.length) * 100 : 0} />

      <div className="rounded-lg border-2 border-primary bg-card p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary">Próxima parada</p>
        {next ? (
          <>
            <p className="mt-1 font-display text-lg font-semibold">{next.address}</p>
            <p className="text-sm text-muted-foreground">{next.recipientName} · {next.unitName || "Sin unidad"}</p>
          </>
        ) : <p className="mt-1 text-sm">No hay paradas pendientes.</p>}
        <Button variant="outline" size="sm" className="mt-3" disabled><LocateFixed className="mr-2 h-4 w-4" />Recalcular desde GPS · Próximamente</Button>
      </div>

      <ul className="space-y-2">
        {stops.map((s) => (
          <li key={s.id} className="rounded-lg border bg-card p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{s.address}</p>
                <p className="truncate text-xs text-muted-foreground">{s.recipientName}</p>
              </div>
              <Badge variant={STATE[s.state].variant}>{STATE[s.state].label}</Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {canTransition(s.state, "complete") && <Button size="sm" variant="success" onClick={() => demoStore.act(s.id, "complete")}><Check className="mr-1 h-4 w-4" />Completar</Button>}
              {canTransition(s.state, "skip") && <Button size="sm" variant="outline" onClick={() => demoStore.act(s.id, "skip")}><SkipForward className="mr-1 h-4 w-4" />Omitir</Button>}
              {canTransition(s.state, "restore") && <Button size="sm" variant="outline" onClick={() => demoStore.act(s.id, "restore")}><RotateCcw className="mr-1 h-4 w-4" />Restaurar</Button>}
              {canTransition(s.state, "remove") && (
                <AlertDialog>
                  <AlertDialogTrigger asChild><Button size="sm" variant="ghost" className="text-destructive"><Trash2 className="mr-1 h-4 w-4" />Eliminar</Button></AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>¿Eliminar esta parada?</AlertDialogTitle>
                      <AlertDialogDescription>Se quitará de la ruta DEMO. Esta acción no se puede deshacer.</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancelar</AlertDialogCancel>
                      <AlertDialogAction onClick={() => demoStore.act(s.id, "remove")}>Eliminar</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}