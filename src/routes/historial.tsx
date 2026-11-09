import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";
import { pageHead } from "@/lib/seo";
import { useDemoStops } from "@/state/demo-store";
export const Route = createFileRoute("/historial")({ head: pageHead("Historial", "Entregas completadas y omitidas registradas en la nube."), component: HistoryPage });
function HistoryPage() {
  const records = useDemoStops().filter(stop => stop.state === "completed" || stop.state === "skipped");
  return <AppShell title="Historial" subtitle={records.length + " entregas finalizadas"}>
    {records.length ? <ul className="space-y-2">{records.map(record => <li key={record.id} className="flex items-center justify-between gap-3 rounded-lg border bg-card p-3"><div className="min-w-0"><p className="truncate text-sm font-medium">{record.address}</p><p className="truncate text-xs text-muted-foreground">{record.recipientName} · {record.unitName}</p></div><Badge variant={record.state === "completed" ? "success" : "warning"}>{record.state === "completed" ? "Completada" : "Omitida"}</Badge></li>)}</ul> : <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">Todavía no hay entregas finalizadas.</div>}
  </AppShell>;
}
