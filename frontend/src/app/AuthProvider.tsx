import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

export type Profile = {
  id: string;
  email: string;
  full_name: string;
  job_title: string | null;
};

type AuthState = {
  session: Session | null;
  profile: Profile | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  // The profile row carries the responder identity every incident action is
  // attributed to. A database trigger creates or adopts it on first sign-in.
  useEffect(() => {
    if (!session?.user) {
      setProfile(null);
      return;
    }
    let live = true;
    supabase
      .from("users")
      .select("id, email, full_name, job_title")
      .eq("auth_id", session.user.id)
      .maybeSingle()
      .then(({ data }) => {
        if (live) setProfile(data as Profile | null);
      });
    return () => {
      live = false;
    };
  }, [session?.user?.id]);

  const value = useMemo<AuthState>(
    () => ({
      session,
      profile,
      loading,
      async signIn(email, password) {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw new Error(error.message);
      },
      async signUp(email, password, fullName) {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: fullName } }
        });
        if (error) throw new Error(error.message);
      },
      async signOut() {
        await supabase.auth.signOut();
      }
    }),
    [session, profile, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
