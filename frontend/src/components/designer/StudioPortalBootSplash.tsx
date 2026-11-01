import ParticleConstellation from "../canvas3d/ParticleConstellation";

type Props = {
  title: string;
  subtitle?: string;
};

export default function StudioPortalBootSplash({ title, subtitle }: Props) {
  return (
    <div
      className="studio-login-shell relative isolate flex min-h-full w-full flex-col items-center justify-center gap-4 px-6"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <ParticleConstellation />
      <div className="relative z-10 flex flex-col items-center gap-4">
        <div className="studio-boot-spinner" aria-hidden />
        <div className="text-center">
          <p className="text-sm font-medium text-white/85">{title}</p>
          <p className="mt-1 text-xs text-cyan-100/45">
            {subtitle ?? "Checking your session…"}
          </p>
        </div>
      </div>
    </div>
  );
}
