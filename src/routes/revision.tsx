import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { MAX_STOPS, findDuplicateIds, reviewStatus, type ReviewStatus } from "@/domain/deliveries";
import { pageHead } from "@/lib/seo";
import { demoStore, useDemoStops } from "@/state/demo-store";

export const Route = createFileRoute("/revision")({
  head: pageHead("Revisión de lectura", "Revise y corrija las entregas leídas antes de agregarlas a la ruta (DEMO)."),
  component: Review,
});

const STATUS: Record<ReviewStatus, { label: string; variant: "success" | "warning" | "danger" }> = {
  ok: { label: "Lista (no validada)", variant: "success" },
  duplicate: { label: "Duplicada", variant: "danger" },
  ambiguous: { label: "Ambigua", variant: "warning" },
  incomplete: { label: "Incompleta", variant: "warning" },
};

function Review() {
  const stops = useDemoStops().filter((s) => s.state !== "removed").slice(0, MAX_STOPS);
  const dups = findDuplicateIds(stops);
  const [confirmed, setConfirmed] = useState(false);

  return (
    <AppShell title="Revisión de lectura" subtitle={`${stops.length} de ${MAX_STOPS} entregas · edite antes de confirmar`}>
      <p className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
        Las direcciones no han sido validadas con ningún servicio externo. Validación: Próximamente.
      </p>
      <div className="space-y-3">
        {stops.map((s, i) => {
          const st = STATUS[reviewStatus(s, dups.has(s.id), s.ambiguous)];
          return (
            <div key={s.id} className="space-y-2 rounded-lg border bg-card p-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-muted-foreground">#{String(i + 1).padStart(2, "0")}</span>
                <Badge variant={st.variant}>{st.label}</Badge>
              </div>
              <div className="grid gap-2 md:grid-cols-3">
                <Input aria-label="Cliente" placeholder="Cliente" value={s.recipientName} onChange={(e) => demoStore.update(s.id, { recipientName: e.target.value })} />
                <Input aria-label="Unidad" placeholder="Unidad" value={s.unitName} onChange={(e) => demoStore.update(s.id, { unitName: e.target.value })} />
                <Input aria-label="Dirección" placeholder="Dirección" value={s.address} onChange={(e) => demoStore.update(s.id, { address: e.target.value })} />
              </div>
            </div>
          );
        })}
      </div>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={confirmed} onCheckedChange={(v) => setConfirmed(v === true)} />
        Revisé los datos y confirmo agregarlos a la ruta
      </label>
      <Button asChild={confirmed} disabled={!confirmed} size="lg" className="w-full">
        {confirmed ? <Link to="/ruta">Agregar a la ruta</Link> : <span>Agregar a la ruta</span>}
      </Button>
    </AppShell>
  );
}