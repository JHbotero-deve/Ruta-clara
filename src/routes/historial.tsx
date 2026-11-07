import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";
import { pageHead } from "@/lib/seo";

export const Route = createFileRoute("/historial")({
  head: pageHead("Historial", "Rutas anteriores de demostración."),
  component: HistoryPage,
});

const ROUTES = [
  { id: "R-DEMO-03", date: "Ruta DEMO 3", stops: 24, done: 24 },
  { id: "R-DEMO-02", date: "Ruta DEMO 2", stops: 30, done: 28 },
  { id: "R-DEMO-01", date: "Ruta DEMO 1", stops: 18, done: 18 },
];

function HistoryPage() {
  return (
    <AppShell title="Historial" subtitle="Rutas anteriores · DEMO · sin persistencia">
      <ul className="space-y-2">
        {ROUTES.map((r) => (
          <li key={r.id} className="flex items-center justify-between rounded-lg border bg-card p-3">
            <div>
              <p className="text-sm font-medium">{r.date}</p>
              <p className="font-mono text-xs text-muted-foreground">{r.id} · {r.stops} paradas</p>
            </div>
            <Badge variant={r.done === r.stops ? "success" : "warning"}>{r.done}/{r.stops} entregadas</Badge>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}