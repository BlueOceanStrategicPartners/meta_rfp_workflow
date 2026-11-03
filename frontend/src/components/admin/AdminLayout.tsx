import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { NavLink } from "react-router-dom";
import StudioSnackbar, { type SnackbarTone } from "../designer/StudioSnackbar";
import { useAppShell } from "../../context/AppShellContext";
import {
  IconDebate,
  IconInventory,
  IconNegotiation,
  IconOccupancy,
  IconOverview,
  IconPricing,
  IconTelemetry,
} from "./AdminIcons";
import "./admin.css";

type RailItem = {
  to: string;
  label: string;
  Icon: ComponentType;
  end?: boolean;
  badge?: string;
};

const RAIL: RailItem[] = [
  { to: "/admin", label: "Overview", Icon: IconOverview, end: true },
  { to: "/admin/debates", label: "Debates", Icon: IconDebate },
  { to: "/admin/pricing", label: "Pricing", Icon: IconPricing },
  { to: "/admin/negotiations", label: "Negotiations", Icon: IconNegotiation },
  { to: "/admin/inventory", label: "Inventory", Icon: IconInventory },
  { to: "/admin/occupancy", label: "Occupancy", Icon: IconOccupancy },
  { to: "/admin/telemetry", label: "Telemetry", Icon: IconTelemetry },
];

type Feedback = {
  /** Show a toast (and announce it to screen readers). */
  notify: (message: string, tone?: SnackbarTone) => void;
  /** Announce text to screen readers only. */
  announce: (message: string) => void;
};

const AdminFeedbackContext = createContext<Feedback | null>(null);

export function useAdminFeedback(): Feedback {
  const ctx = useContext(AdminFeedbackContext);
  if (!ctx) throw new Error("useAdminFeedback must be used inside AdminLayout");
  return ctx;
}

/** Announce a polling/load error once each time it appears. */
export function useAnnounceError(error: unknown, message: string) {
  const { announce } = useAdminFeedback();
  const had = useRef(false);
  useEffect(() => {
    if (error && !had.current) announce(message);
    had.current = !!error;
  }, [announce, error, message]);
}

/** Root wrapper shared by the layout and the sign-in views (theme + admin colours). */
export function AdminShell({
  children,
  className = "",
  scrollable = false,
}: {
  children: ReactNode;
  className?: string;
  /** Let the shell itself scroll (sign-in view on short screens). */
  scrollable?: boolean;
}) {
  const { theme } = useAppShell();
  const base = theme === "light" ? "designer-shell-light" : "text-white";
  const overflow = scrollable ? "overflow-y-auto overflow-x-hidden studio-scroll" : "overflow-hidden";
  return (
    <div className={`admin-root ${base} flex h-full min-h-0 flex-col ${overflow} ${className}`}>
      {children}
    </div>
  );
}

export default function AdminLayout({ email, children }: { email?: string | null; children: ReactNode }) {
  const [snack, setSnack] = useState<{ open: boolean; message: string; tone: SnackbarTone }>({
    open: false,
    message: "",
    tone: "info",
  });
  const [liveText, setLiveText] = useState("");

  const announce = useCallback((message: string) => {
    // Clear first so repeating the same text is announced again.
    setLiveText("");
    window.setTimeout(() => setLiveText(message), 50);
  }, []);

  // StudioSnackbar is its own polite live region, so toasts are not re-announced here.
  const notify = useCallback((message: string, tone: SnackbarTone = "info") => {
    setSnack({ open: true, message, tone });
  }, []);

  const closeSnack = useCallback(() => setSnack((s) => ({ ...s, open: false })), []);

  const feedback = useMemo(() => ({ notify, announce }), [notify, announce]);

  return (
    <AdminFeedbackContext.Provider value={feedback}>
      <AdminShell>
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden px-4 pb-[var(--studio-safe-bottom)] pt-3 sm:flex-row sm:px-6">
          <aside className="studio-shell-panel flex max-h-[32vh] w-full shrink-0 flex-col sm:max-h-none sm:w-60">
            <div className="studio-panel-header !min-h-[4rem] hidden sm:flex">
              <div>
                <p className="studio-panel-kicker">Admin</p>
                <h2 className="font-semibold">Command Center</h2>
                {email ? <p className="admin-faint mt-0.5 truncate text-[11px]">{email}</p> : null}
              </div>
            </div>
            <nav aria-label="Admin modules" className="min-h-0 flex-1">
              <ul className="studio-scroll flex h-full flex-row gap-1 overflow-x-auto px-[var(--studio-inset-x)] py-2.5 sm:flex-col sm:overflow-y-auto sm:overflow-x-hidden sm:py-3">
                {RAIL.map(({ to, label, Icon, end, badge }) => (
                  <li key={to} className="shrink-0">
                    <NavLink
                      to={to}
                      end={end}
                      className={({ isActive }) => `admin-rail-link sm:w-full ${isActive ? "is-active" : ""}`}
                    >
                      <Icon />
                      <span>{label}</span>
                      {badge ? <span className="admin-rail-badge">{badge}</span> : null}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
          </aside>
          <section className="studio-shell-panel relative flex min-h-0 min-w-0 flex-1 flex-col">
            {children}
          </section>
        </div>
        <div className="admin-sr-only" aria-live="polite" aria-atomic="true">
          {liveText}
        </div>
        <StudioSnackbar open={snack.open} message={snack.message} tone={snack.tone} onClose={closeSnack} />
      </AdminShell>
    </AdminFeedbackContext.Provider>
  );
}
