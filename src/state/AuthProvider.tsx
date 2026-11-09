import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getCurrentUser, getValidSession, isSupabaseConfigured, signIn as authSignIn, signOut as authSignOut, signUp as authSignUp, type AuthSession, type AuthUser } from "@/lib/supabase-auth";
interface AuthContextValue {
  user: AuthUser | null;
  session: AuthSession | null;
  loading: boolean;
  configured: boolean;
  signIn(email: string, password: string): Promise<void>;
  signUp(email: string, password: string, fullName: string, companyName: string, inviteCode: string): Promise<boolean>;
  signOut(): Promise<void>;
}
const AuthContext = createContext<AuthContextValue | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    const restore = async () => {
      const current = await getValidSession();
      if (!active) return;
      if (!current) { setSession(null); setUser(null); setLoading(false); return; }
      try {
        const currentUser = await getCurrentUser(current);
        if (active) { setSession(current); setUser(currentUser); }
      } catch {
        await authSignOut();
        if (active) { setSession(null); setUser(null); }
      } finally { if (active) setLoading(false); }
    };
    void restore();
    const onStorage = () => { void restore(); };
    window.addEventListener("storage", onStorage);
    return () => { active = false; window.removeEventListener("storage", onStorage); };
  }, []);
  const value = useMemo<AuthContextValue>(() => ({
    user, session, loading, configured: isSupabaseConfigured,
    async signIn(email, password) { const next = await authSignIn(email, password); setSession(next); setUser(next.user); },
    async signUp(email, password, fullName, companyName) {
      const next = await authSignUp(email, password, fullName, companyName, inviteCode);
      if (next) { setSession(next); setUser(next.user); return true; }
      return false;
    },
    async signOut() { await authSignOut(); setSession(null); setUser(null); },
  }), [user, session, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth debe utilizarse dentro de AuthProvider.");
  return value;
}
