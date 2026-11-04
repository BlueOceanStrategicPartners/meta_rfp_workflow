import type { ClientSessionState } from "../../lib/clientSession";

type Props = {
  session?: ClientSessionState;
};

function formatWhen(at?: string) {
  if (!at) return "";
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return at;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function roleLabel(role: string) {
  const r = role.toLowerCase();
  if (r === "user" || r === "client") return "You";
  if (r === "agent" || r === "assistant") return "Agent";
  return role;
}

const DIALOGUE_EVENT_TYPES = new Set(["voice", "assistant_reply", "card_edit"]);

export default function ClientSessionTimeline({ session }: Props) {
  const events = (session?.events || []).slice(-8);
  const transcript = (session?.transcript || []).slice(-6);
  const showTranscript = transcript.length > 0 && !events.some((ev) => DIALOGUE_EVENT_TYPES.has(String(ev.type || "")));

  if (events.length === 0 && transcript.length === 0) return null;

  return (
    <div className="client-side-card client-side-session-activity client-side-timeline shrink-0 px-3 py-2.5">
      <p className="client-side-card__kicker mb-2">Session activity</p>
      <ul className="space-y-2">
        {events.map((ev, i) => (
          <li
            key={`ev-${ev.at || i}-${ev.type || "event"}`}
            className="client-side-timeline-item text-[11px] leading-snug"
          >
            {ev.at && (
              <time className="client-side-timeline-item__time block text-[10px]">{formatWhen(ev.at)}</time>
            )}
            <span className="client-side-timeline-item__body">
              {ev.type && (
                <span className="client-side-timeline-item__type mr-1 font-medium uppercase tracking-wide">
                  {ev.type}
                </span>
              )}
              {ev.summary || "—"}
            </span>
          </li>
        ))}
        {showTranscript &&
          transcript.map((turn, i) => (
            <li
              key={`tx-${turn.at || i}-${turn.role}`}
              className="client-side-timeline-item client-side-timeline-item--transcript text-[11px] leading-snug"
            >
              {turn.at && (
                <time className="client-side-timeline-item__time block text-[10px]">{formatWhen(turn.at)}</time>
              )}
              <span className="client-side-timeline-item__body">
                <span className="client-side-timeline-item__type mr-1 font-medium">{roleLabel(turn.role)}:</span>
                {turn.text}
              </span>
            </li>
          ))}
      </ul>
    </div>
  );
}
