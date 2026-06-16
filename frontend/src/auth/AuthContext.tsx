import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import type { AuthConfig, Me } from "@/lib/types";

interface RegisterPayload {
  email: string;
  password: string;
  display_name: string;
}

interface AuthContextValue {
  me: Me | null;
  config: AuthConfig | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await api.get<Me>("/api/auth/me"));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    api
      .get<AuthConfig>("/api/auth/config")
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setMe(await api.post<Me>("/api/auth/login", { email, password }));
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    setMe(await api.post<Me>("/api/auth/register", payload));
  }, []);

  const logout = useCallback(async () => {
    await api.post("/api/auth/logout");
    setMe(null);
  }, []);

  return (
    <AuthContext.Provider value={{ me, config, loading, refresh, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
