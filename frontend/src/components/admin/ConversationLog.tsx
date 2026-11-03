import { useEffect, useRef } from "react";
import type { ConversationMessage } from "../../lib/adminApi";
import { formatDateTime } from "../../lib/adminFormat";

const SPEAKER: Record<ConversationMessage["who"], string> = {
  client: "Client",
  agent: "AI agent",
  admin: "You (admin)",
  auto: "Automatic reply",
  system: "",
};

function speakerLabel(m: ConversationMessage): string {
  if (m.who === "admin" && m.by) return `Admin · ${m.by}`;
  return SPEAKER[m.who];
}

/** Chat-style transcript of one negotiation. Client on the left; agent, admin and auto replies on the right. */
export default function ConversationLog({ messages }: { messages: ConversationMessage[] }) {
  const boxRef = useRef<HTMLDivElement | null>(null);
  const count = messages.length;

  // Keep the newest message in view inside the box (without scrolling the whole page).
  useEffect(() => {
    const box = boxRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [count]);

  if (!count) {
    return (
      <div className="studio-empty-list">
        No messages yet. What the client says, and every reply, will appear here.
      </div>
    );
  }

  return (
    <div ref={boxRef} className="admin-convo studio-scroll">
      <ol className="admin-convo-list" aria-label="Conversation with the client">
        {messages.map((m, i) =>
          m.who === "system" ? (
            <li key={`${m.at}-${i}`} className="admin-convo-marker">
              {m.text} · {formatDateTime(m.at)}
            </li>
          ) : (
            <li key={`${m.at}-${i}`} className={`admin-convo-row admin-convo-row--${m.who === "client" ? "in" : "out"}`}>
              <div className={`admin-convo-bubble admin-convo-bubble--${m.who}`}>
                <div className="admin-convo-meta">
                  <span>{speakerLabel(m)}</span>
                  <time dateTime={m.at}>{formatDateTime(m.at)}</time>
                </div>
                <p className="admin-convo-text">{m.text}</p>
              </div>
            </li>
          ),
        )}
      </ol>
    </div>
  );
}
