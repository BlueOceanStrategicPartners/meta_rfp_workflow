import { motion } from "framer-motion";

type Props = {
  cards: Record<string, unknown>;
  onSubmit: (payload: Record<string, unknown>) => void;
};

function display(value: unknown) {
  if (value == null || value === "") return "—";
  return String(value);
}

export default function AgentCardDeck({ cards, onSubmit }: Props) {
  const meeting = (cards.meeting_space as Record<string, unknown>) || {};
  const quote = (cards.live_quote as Record<string, unknown>) || {};
  const overview = (cards.event_overview as Record<string, unknown>) || {};

  return (
    <div className="fixed right-4 top-20 w-80 space-y-3 max-h-[70vh] overflow-auto z-30 pointer-events-auto">
      <Card title="Event Overview" amber={(overview.amber_fields as string[]) || []}>
        <p>{display(overview.company_name)}</p>
        <p className="text-xs text-white/60">
          {display(overview.check_in_date)} → {display(overview.check_out_date)}
        </p>
      </Card>
      <Card title="Meeting Space">
        <label className="text-xs block">
          Headcount
          <input
            type="number"
            className="w-full mt-1 bg-black/30 rounded px-2 py-1"
            defaultValue={Number(meeting.headcount || 0)}
            id="headcount-input"
          />
        </label>
      </Card>
      <Card title="Live Dynamic Quote">
        <p>Estimated package rate: {display(quote.anchor_price)}</p>
        <button
          type="button"
          className="mt-2 w-full py-2 rounded bg-emerald-500/80 text-sm"
          onClick={() =>
            onSubmit({
              meeting_space: {
                ...meeting,
                headcount: Number(
                  (document.getElementById("headcount-input") as HTMLInputElement)?.value || 0,
                ),
              },
            })
          }
        >
          Submit Changes
        </button>
      </Card>
    </div>
  );
}

function Card({
  title,
  children,
  amber = [],
}: {
  title: string;
  children: React.ReactNode;
  amber?: string[];
}) {
  return (
    <motion.div
      layout
      className={`p-3 rounded-xl border ${amber.length ? "border-amber-400/60" : "border-white/10"} bg-black/40 backdrop-blur`}
    >
      <h3 className="text-sm font-medium mb-2">{title}</h3>
      {children}
    </motion.div>
  );
}
