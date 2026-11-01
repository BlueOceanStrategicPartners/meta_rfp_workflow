import { renderDesignerMarkdown } from "../../lib/designerMarkdown";
import type { ChatMessage } from "../../lib/designerApi";

type Props = {
  msg: ChatMessage;
  pinned?: boolean;
  onTogglePin?: () => void;
};

export default function ChatMessageView({ msg, pinned, onTogglePin }: Props) {
  const isUser = msg.role === "user";
  const time = msg.ts ? new Date(msg.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : null;
  const body =
    msg.role === "assistant" ? renderDesignerMarkdown(msg.content) : msg.content.replace(/\n/g, "<br/>");

  return (
    <div
      className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? "ml-auto bg-gradient-to-br from-violet-700/85 to-indigo-800/85"
          : "border border-white/10 bg-white/[0.06]"
      } ${pinned ? "ring-1 ring-amber-400/50" : ""}`}
    >
      <div className="mb-1 flex items-center justify-between gap-2 text-[10px] uppercase tracking-wide text-white/45">
        <span>{isUser ? "You" : "Design Agent"}</span>
        <span className="flex items-center gap-2 normal-case">
          {time && <time dateTime={msg.ts}>{time}</time>}
          {onTogglePin && (
            <button
              type="button"
              onClick={onTogglePin}
              className="rounded px-1 hover:text-amber-200 focus-visible:ring-2 focus-visible:ring-violet-500"
              aria-label={pinned ? "Unpin message" : "Pin message"}
            >
              {pinned ? "📌" : "📍"}
            </button>
          )}
        </span>
      </div>
      {isUser ? (
        <div className="whitespace-pre-wrap">{msg.content}</div>
      ) : (
        <div
          className="prose-invert [&_.md-pre]:mt-2 [&_.md-pre]:overflow-x-auto [&_.md-pre]:rounded-lg [&_.md-pre]:bg-black/40 [&_.md-pre]:p-2 [&_.md-code]:rounded [&_.md-code]:bg-black/30 [&_.md-code]:px-1"
          dangerouslySetInnerHTML={{ __html: body }}
        />
      )}
    </div>
  );
}
