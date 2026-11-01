import { useDebateObservatory } from "../hooks/useBidirectionalAgentUI";

const MODULES = [
  "Map Studio",
  "Debate Observatory",
  "Pricing & XGBoost",
  "Negotiation Monitor",
  "Inventory CMS",
  "Occupancy Sync",
  "SLA Telemetry",
];

export default function AdminPortal() {
  const { debates } = useDebateObservatory();

  return (
    <div className="h-full min-h-0 overflow-y-auto p-6 space-y-6">
      <h1 className="text-2xl">Admin Command Center</h1>
      <div className="grid md:grid-cols-3 gap-3">
        {MODULES.map((name) => (
          <div key={name} className="p-4 rounded-xl border border-white/10 bg-black/30">
            {name}
          </div>
        ))}
      </div>
      <section>
        <h2 className="text-lg mb-2">Live 3-Agent Debate Observatory</h2>
        <pre className="text-xs bg-black/50 p-3 rounded overflow-auto max-h-64">
          {JSON.stringify(debates, null, 2)}
        </pre>
      </section>
    </div>
  );
}
