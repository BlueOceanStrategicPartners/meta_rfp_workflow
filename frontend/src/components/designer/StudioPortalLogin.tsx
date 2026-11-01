import { motion } from "framer-motion";
import ParticleConstellation from "../canvas3d/ParticleConstellation";

const EASE: [number, number, number, number] = [0.45, 0.05, 0.25, 1];

function IconMicrosoft() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" aria-hidden>
      <rect x="3" y="3" width="8.5" height="8.5" fill="#f25022" />
      <rect x="12.5" y="3" width="8.5" height="8.5" fill="#7fba00" />
      <rect x="3" y="12.5" width="8.5" height="8.5" fill="#00a4ef" />
      <rect x="12.5" y="12.5" width="8.5" height="8.5" fill="#ffb900" />
    </svg>
  );
}

function IconGoogle() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#4285F4"
        d="M22 12.24c0-.82-.07-1.42-.22-2.05H12v3.72h5.76c-.12 1.02-.77 2.55-2.21 3.55l-.02.14 3.2 2.48.22.02C20.94 18.3 22 15.45 22 12.24z"
      />
      <path
        fill="#34A853"
        d="M12 22c2.97 0 5.46-.98 7.28-2.66l-3.47-2.69c-.93.63-2.17 1.06-3.81 1.06-2.91 0-5.38-1.96-6.26-4.6l-.13.01-3.39 2.62-.04.12C4.48 19.53 7.99 22 12 22z"
      />
      <path
        fill="#FBBC05"
        d="M5.74 13.11c-.22-.65-.35-1.35-.35-2.11s.13-1.46.34-2.11l-.01-.15-3.43-2.65-.11.05C1.27 8.5 1 10.21 1 12s.27 3.5.74 5.01l3.99-2.9z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c2.07 0 3.47.9 4.27 1.65l3.12-3.04C17.43 1.18 14.97 0 12 0 7.99 0 4.48 2.47 2.93 6.01l3.99 2.9C7.62 6.71 10.09 4.75 12 4.75z"
      />
    </svg>
  );
}

type Props = {
  title: string;
  subtitle?: string;
  error?: string | null;
  email: string;
  password: string;
  busy?: boolean;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: () => void | Promise<void>;
  onMockSso?: (provider: "microsoft" | "google") => void | Promise<void>;
};

export default function StudioPortalLogin({
  title,
  subtitle = "Sign in with your designer account",
  error,
  email,
  password,
  busy,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  onMockSso,
}: Props) {
  const handleSso = (provider: "microsoft" | "google") => {
    if (onMockSso) void onMockSso(provider);
  };

  return (
    <div className="studio-login-shell relative isolate flex min-h-full w-full items-center justify-center overflow-hidden px-4 py-10">
      <ParticleConstellation />
      <motion.div
        className="studio-login-card relative z-10 w-full max-w-[420px]"
        initial={{ opacity: 0, y: 18, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.55, ease: EASE }}
      >
        <div className="mb-6">
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-400/80">
            Hospitality RFP Engine
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">{title}</h1>
          <p className="mt-1.5 text-sm text-cyan-100/45">{subtitle}</p>
        </div>

        {error && (
          <p className="mb-4 rounded-lg border border-red-500/35 bg-red-950/50 px-3 py-2 text-sm text-red-200">
            {error}
          </p>
        )}

        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void onSubmit();
          }}
        >
          <label className="block">
            <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-cyan-200/50">
              Email
            </span>
            <input
              type="email"
              autoComplete="username"
              className="studio-login-field"
              value={email}
              onChange={(e) => onEmailChange(e.target.value)}
              disabled={busy}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-cyan-200/50">
              Password
            </span>
            <input
              type="password"
              autoComplete="current-password"
              className="studio-login-field"
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
              disabled={busy}
            />
          </label>
          <motion.button
            type="submit"
            disabled={busy}
            className="studio-login-primary"
            whileHover={busy ? undefined : { scale: 1.01 }}
            whileTap={busy ? undefined : { scale: 0.98 }}
            transition={{ duration: 0.2, ease: EASE }}
          >
            {busy ? "Signing in…" : "Sign in with email"}
          </motion.button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <span className="h-px flex-1 bg-cyan-500/15" aria-hidden />
          <span className="text-[11px] font-medium uppercase tracking-wide text-cyan-100/35">Or continue with</span>
          <span className="h-px flex-1 bg-cyan-500/15" aria-hidden />
        </div>

        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          <motion.button
            type="button"
            disabled={busy}
            className="studio-sso-btn"
            onClick={() => handleSso("microsoft")}
            whileHover={busy ? undefined : { scale: 1.02 }}
            whileTap={busy ? undefined : { scale: 0.98 }}
          >
            <IconMicrosoft />
            <span>Microsoft</span>
          </motion.button>
          <motion.button
            type="button"
            disabled={busy}
            className="studio-sso-btn"
            onClick={() => handleSso("google")}
            whileHover={busy ? undefined : { scale: 1.02 }}
            whileTap={busy ? undefined : { scale: 0.98 }}
          >
            <IconGoogle />
            <span>Google</span>
          </motion.button>
        </div>
      </motion.div>
    </div>
  );
}
