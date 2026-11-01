import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { isStudioRole } from "../lib/authTokens";
import { authMe } from "../lib/designerApi";

export type AppTheme = "dark" | "light";

const THEME_KEY = "rfp-app-theme";

type AppShellContextValue = {
  theme: AppTheme;
  setTheme: (theme: AppTheme) => void;
  toggleTheme: () => void;
  designerAuthed: boolean;
  setDesignerAuthed: (value: boolean) => void;
  authBootstrapped: boolean;
};

const AppShellContext = createContext<AppShellContextValue | null>(null);

function readStoredTheme(): AppTheme {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function AppShellProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<AppTheme>(() => readStoredTheme());
  const [designerAuthed, setDesignerAuthed] = useState(false);
  const [authBootstrapped, setAuthBootstrapped] = useState(false);

  const setTheme = useCallback((next: AppTheme) => {
    setThemeState(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [setTheme, theme]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const me = await authMe();
        if (!cancelled && me.authenticated && isStudioRole(me.role)) {
          setDesignerAuthed(true);
        }
      } catch {
        /* not signed in */
      } finally {
        if (!cancelled) setAuthBootstrapped(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      designerAuthed,
      setDesignerAuthed,
      authBootstrapped,
    }),
    [theme, setTheme, toggleTheme, designerAuthed, authBootstrapped],
  );

  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShell() {
  const ctx = useContext(AppShellContext);
  if (!ctx) throw new Error("useAppShell must be used within AppShellProvider");
  return ctx;
}
