import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import { History, Home, ListChecks, Map, ScanLine, ShieldCheck, ClipboardCheck, LogOut, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/state/AuthProvider";
const NAV = [
  { to: "/", label: "Inicio", icon: Home },
  { to: "/escaner", label: "Escáner", icon: ScanLine },
  { to: "/revision", label: "Revisión", icon: ClipboardCheck },
  { to: "/ruta", label: "Ruta", icon: Map },
  { to: "/entregas", label: "Entregas", icon: ListChecks },
  { to: "/equipo", label: "Equipo", icon: Users },
  { to: "/historial", label: "Historial", icon: History },
  { to: "/seguridad", label: "Seguridad", icon: ShieldCheck },
] as const;
const MOBILE = ["/", "/escaner", "/ruta", "/entregas", "/seguridad"];
export function DemoBadge({ children = "DEMO" }: { children?: ReactNode }) {
  return <Badge variant="demo">{children}</Badge>;
}
export function AppShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  const { user, loading, signOut } = useAuth();
  const navigate = useNavigate();
  useEffect(() => { if (!loading && !user) void navigate({ to: "/login" }); }, [loading, user, navigate]);
  async function handleSignOut() { await signOut(); await navigate({ to: "/login" }); }
  if (loading || !user) return <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">Verificando sesión...</div>;
  return <div className="min-h-screen bg-background md:flex">
    <aside className="hidden md:sticky md:top-0 md:flex md:h-screen md:w-60 md:flex-col md:border-r md:bg-sidebar md:p-4">
      <div className="mb-8 px-2"><p className="font-display text-lg font-semibold text-sidebar-foreground">Ruta Clara</p><p className="text-xs text-muted-foreground">Operación de última milla</p></div>
      <nav className="flex flex-col gap-1">{NAV.map(({ to, label, icon: Icon }) => <Link key={to} to={to} activeOptions={{ exact: true }} className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent data-[status=active]:bg-sidebar-primary data-[status=active]:text-sidebar-primary-foreground"><Icon className="h-4 w-4" />{label}</Link>)}</nav>
    </aside>
    <div className="flex-1 pb-24 md:pb-8">
      <header className="sticky top-0 z-10 border-b bg-background/95 px-4 py-3 backdrop-blur md:px-8"><div className="mx-auto flex max-w-4xl items-center justify-between gap-3"><div><h1 className="font-display text-lg font-semibold">{title}</h1>{subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}</div><div className="flex items-center gap-2"><span className="hidden max-w-48 truncate text-xs text-muted-foreground sm:block">{user.email}</span><Button variant="outline" size="sm" onClick={() => void handleSignOut()}><LogOut className="mr-1 h-4 w-4" />Salir</Button></div></div></header>
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-4 md:px-8 md:py-6">{children}</main>
    </div>
    <nav className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t bg-card md:hidden">{NAV.filter(n => MOBILE.includes(n.to)).map(({ to, label, icon: Icon }) => <Link key={to} to={to} activeOptions={{ exact: true }} className="flex flex-col items-center gap-1 py-2 text-[11px] text-muted-foreground data-[status=active]:text-primary"><Icon className="h-5 w-5" />{label}</Link>)}</nav>
  </div>;
}
export function Stat({ label, value, tone = "default" }: { label: string; value: ReactNode; tone?: "default" | "success" | "warning" }) {
  const toneCls = tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : "text-foreground";
  return <div className="rounded-lg border bg-card p-3"><p className="text-xs text-muted-foreground">{label}</p><p className={\`font-display text-2xl font-semibold \${toneCls}\`}>{value}</p></div>;
}
