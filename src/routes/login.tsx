import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "@/state/AuthProvider";
export const Route = createFileRoute("/login")({ component: LoginPage });
function LoginPage() {
  const { user, loading, configured, signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (user && !loading) void navigate({ to: "/" }); }, [user, loading, navigate]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage(""); setBusy(true);
    try {
      if (mode === "login") { await signIn(email.trim(), password); await navigate({ to: "/" }); }
      else {
        const authenticated = await signUp(email.trim(), password, fullName.trim(), companyName.trim());
        if (authenticated) await navigate({ to: "/" });
        else setMessage("Cuenta creada. Revisa tu correo para confirmar la dirección antes de iniciar sesión.");
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Ocurrió un error."); }
    finally { setBusy(false); }
  }
  return <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
    <section className="w-full max-w-md rounded-xl border bg-card p-6 shadow-sm">
      <p className="font-display text-2xl font-bold">Ruta Clara</p>
      <p className="mt-1 text-sm text-muted-foreground">Operación de entregas · equipos de última milla</p>
      {!configured ? <div className="mt-6 rounded-lg border border-warning/40 bg-warning-soft p-4 text-sm">La autenticación aún no está conectada. Configura <code>VITE_SUPABASE_URL</code> y <code>VITE_SUPABASE_ANON_KEY</code> en el entorno de despliegue.</div> : <>
        <div className="mt-6 grid grid-cols-2 rounded-lg bg-muted p-1 text-sm">
          <button type="button" onClick={() => { setMode("login"); setError(""); }} className={\`rounded-md px-3 py-2 \${mode === "login" ? "bg-background shadow-sm" : "text-muted-foreground"}\`}>Iniciar sesión</button>
          <button type="button" onClick={() => { setMode("signup"); setError(""); }} className={\`rounded-md px-3 py-2 \${mode === "signup" ? "bg-background shadow-sm" : "text-muted-foreground"}\`}>Crear empresa</button>
        </div>
        <form onSubmit={submit} className="mt-5 space-y-4">
          {mode === "signup" && <>
            <label className="block text-sm font-medium">Nombre completo<input required value={fullName} onChange={e => setFullName(e.target.value)} autoComplete="name" className="mt-1 h-10 w-full rounded-md border bg-background px-3" /></label>
            <label className="block text-sm font-medium">Empresa<input required value={companyName} onChange={e => setCompanyName(e.target.value)} autoComplete="organization" className="mt-1 h-10 w-full rounded-md border bg-background px-3" /></label>
          </>}
          <label className="block text-sm font-medium">Correo electrónico<input required type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" className="mt-1 h-10 w-full rounded-md border bg-background px-3" /></label>
          <label className="block text-sm font-medium">Contraseña<input required minLength={8} type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} className="mt-1 h-10 w-full rounded-md border bg-background px-3" /></label>
          {error && <p role="alert" className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
          {message && <p role="status" className="rounded-md bg-success/10 p-3 text-sm">{message}</p>}
          <button disabled={busy} className="h-11 w-full rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy ? "Procesando..." : mode === "login" ? "Entrar" : "Crear cuenta de empresa"}</button>
        </form>
      </>}
      <p className="mt-5 text-xs text-muted-foreground">El acceso está protegido por autenticación. Los datos de cada empresa se aíslan en la base de datos.</p>
    </section>
  </main>;
}
