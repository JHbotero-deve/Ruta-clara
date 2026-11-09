import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { Check, LocateFixed, RotateCcw, SkipForward, Trash2, Plus } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { canTransition, type DeliveryState } from "@/domain/deliveries";
import { pageHead } from "@/lib/seo";
import { getMyMembership, listTeamMembers } from "@/lib/supabase-data";
import { demoStore, useDemoStops } from "@/state/demo-store";
export const Route = createFileRoute("/entregas")({ head: pageHead("Entregas", "Gestiona las entregas de tu empresa."), component: Deliveries });
const STATE: Record<DeliveryState, { label: string; variant: "success" | "muted" | "warning" | "danger" }> = {
  pending: { label: "Pendiente", variant: "muted" }, completed: { label: "Completada", variant: "success" }, skipped: { label: "Omitida", variant: "warning" }, removed: { label: "Eliminada", variant: "danger" },
};
type TeamMember = Awaited<ReturnType<typeof listTeamMembers>>[number];
function Deliveries() {
  const stops = useDemoStops().filter(s => s.state !== "removed");
  const done = stops.filter(s => s.state === "completed").length;
  const next = stops.find(s => s.state === "pending");
  const [role, setRole] = useState<"owner" | "admin" | "driver" | null>(null);
  const [drivers, setDrivers] = useState<TeamMember[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [address, setAddress] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [unitName, setUnitName] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    void getMyMembership().then(m => setRole(m.role)).catch(e => setError(e.message));
    void listTeamMembers().then(m => setDrivers(m.filter(x => x.role === "driver"))).catch(() => undefined);
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setSaving(true);
    try {
      await demoStore.add({ address: address.trim(), recipientName: recipientName.trim(), unitName: unitName.trim() }, assignedTo || undefined);
      setAddress(""); setRecipientName(""); setUnitName(""); setAssignedTo(""); setShowForm(false);
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo crear la entrega."); }
    finally { setSaving(false); }
  }
  return <AppShell title="Entregas" subtitle={done + " de " + stops.length + " completadas"}>
    <Progress value={stops.length ? done / stops.length * 100 : 0} />
    {role !== "driver" && <section className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between"><h2 className="font-semibold">Nueva entrega</h2><Button size="sm" variant="outline" onClick={() => setShowForm(!showForm)}><Plus className="mr-1 h-4 w-4" />{showForm ? "Cerrar" : "Agregar"}</Button></div>
      {showForm && <form onSubmit={submit} className="mt-4 space-y-3">
        <input required placeholder="Dirección de entrega" value={address} onChange={e => setAddress(e.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm" />
        <input required placeholder="Cliente / destinatario" value={recipientName} onChange={e => setRecipientName(e.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm" />
        <input required placeholder="Unidad / conjunto" value={unitName} onChange={e => setUnitName(e.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm" />
        <select value={assignedTo} onChange={e => setAssignedTo(e.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="">Sin asignar</option>{drivers.map(driver => <option key={driver.user_id} value={driver.user_id}>{driver.full_name || driver.email || driver.user_id}</option>)}</select>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button disabled={saving} type="submit" className="w-full">{saving ? "Guardando..." : "Guardar entrega"}</Button>
      </form>}
    </section>}
    <div className="rounded-lg border-2 border-primary bg-card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">Próxima parada</p>
      {next ? <><p className="mt-1 font-display text-lg font-semibold">{next.address}</p><p className="text-sm text-muted-foreground">{next.recipientName} · {next.unitName || "Sin unidad"}</p></> : <p className="mt-1 text-sm">No hay paradas pendientes.</p>}
      <Button variant="outline" size="sm" className="mt-3" disabled><LocateFixed className="mr-2 h-4 w-4" />Recalcular desde GPS · Pendiente</Button>
    </div>
    <ul className="space-y-2">
      {stops.map(s => <li key={s.id} className="rounded-lg border bg-card p-3">
        <div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-medium">{s.address}</p><p className="truncate text-xs text-muted-foreground">{s.recipientName} · {s.unitName}</p></div><Badge variant={STATE[s.state].variant}>{STATE[s.state].label}</Badge></div>
        <div className="mt-3 flex flex-wrap gap-2">
          {canTransition(s.state, "complete") && <Button size="sm" variant="success" onClick={() => void demoStore.act(s.id, "complete")}><Check className="mr-1 h-4 w-4" />Completar</Button>}
          {canTransition(s.state, "skip") && <Button size="sm" variant="outline" onClick={() => void demoStore.act(s.id, "skip")}><SkipForward className="mr-1 h-4 w-4" />Omitir</Button>}
          {canTransition(s.state, "restore") && <Button size="sm" variant="outline" onClick={() => void demoStore.act(s.id, "restore")}><RotateCcw className="mr-1 h-4 w-4" />Restaurar</Button>}
          {role !== "driver" && canTransition(s.state, "remove") && <AlertDialog><AlertDialogTrigger asChild><Button size="sm" variant="ghost" className="text-destructive"><Trash2 className="mr-1 h-4 w-4" />Eliminar</Button></AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>¿Eliminar esta entrega?</AlertDialogTitle><AlertDialogDescription>Se quitará de la lista de entregas.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancelar</AlertDialogCancel><AlertDialogAction onClick={() => void demoStore.act(s.id, "remove")}>Eliminar</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>}
        </div>
      </li>)}
      {stops.length === 0 && <li className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">Todavía no hay entregas. Crea una para comenzar.</li>}
    </ul>
  </AppShell>;
}
