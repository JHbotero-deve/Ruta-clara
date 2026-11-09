import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { createTeamInvite, getMyMembership, listTeamMembers } from "@/lib/supabase-data";
type Member = Awaited<ReturnType<typeof listTeamMembers>>[number];
export const Route = createFileRoute("/equipo")({ component: TeamPage });
function TeamPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [role, setRole] = useState<"driver" | "admin">("driver");
  const [invite, setInvite] = useState("");
  const [loading, setLoading] = useState(true);
  const [canInvite, setCanInvite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function refresh() {
    setLoading(true);
    try { setMembers(await listTeamMembers()); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo cargar el equipo."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); void getMyMembership().then(m => setCanInvite(m.role === "owner" || m.role === "admin")); }, []);
  async function generateInvite() {
    setBusy(true); setError(""); setInvite("");
    try { setInvite(await createTeamInvite(role)); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo crear la invitación."); }
    finally { setBusy(false); }
  }
  return <AppShell title="Equipo" subtitle="Miembros y accesos de tu empresa">
    <section className="rounded-lg border bg-card p-4">
      <h2 className="font-semibold">Invitar a un repartidor o administrador</h2>
      <p className="mt-1 text-sm text-muted-foreground">Genera un código de un solo uso válido durante 7 días. Compártelo con la persona para que cree su cuenta y se una a esta empresa.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <select value={role} onChange={e => setRole(e.target.value as "driver" | "admin")} className="h-10 rounded-md border bg-background px-3 text-sm">
          <option value="driver">Repartidor</option><option value="admin">Administrador</option>
        </select>
        <Button disabled={busy} onClick={() => void generateInvite()}>{busy ? "Generando..." : "Generar invitación"}</Button>
      </div>
      {invite && <div className="mt-3 rounded-md border bg-muted p-3"><p className="text-xs font-medium">Código de invitación · compartir una sola vez</p><p className="mt-2 break-all font-mono text-sm">{invite}</p><Button className="mt-2" size="sm" variant="outline" onClick={() => void navigator.clipboard.writeText(invite)}>Copiar código</Button></div>}
      {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
    </section>
    <section className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between"><h2 className="font-semibold">Miembros activos</h2><Button size="sm" variant="outline" onClick={() => void refresh()}>Actualizar</Button></div>
      {loading ? <p className="mt-3 text-sm text-muted-foreground">Cargando equipo...</p> : <ul className="mt-3 divide-y">{members.map(member => <li key={member.user_id} className="flex items-center justify-between gap-3 py-3"><div className="min-w-0"><p className="truncate text-sm font-medium">{member.full_name || member.email || "Usuario"}</p><p className="truncate text-xs text-muted-foreground">{member.email}</p></div><span className="rounded-full bg-muted px-2 py-1 text-xs capitalize">{member.role === "owner" ? "Propietario" : member.role === "admin" ? "Administrador" : "Repartidor"}</span></li>)}</ul>}
    </section>
  </AppShell>;
}
