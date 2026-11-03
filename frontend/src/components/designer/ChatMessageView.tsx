import { renderDesignerMarkdown } from "../../lib/designerMarkdown";
import type { ChatMessage } from "../../lib/designerApi";
import { userMessageDisplayParts } from "../../lib/previewTargetChat";
import PreviewTargetActionCard from "./PreviewTargetActionCard";

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
  const userParts = isUser ? userMessageDisplayParts(msg) : null;
  const userText = userParts?.text?.trim() || "";
  const previewTarget = userParts?.previewTarget ?? null;

  return (
    <div className={`flex w-full min-w-0 ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`min-w-0 max-w-[min(100%,42rem)] overflow-hidden rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-gradient-to-br from-violet-700/85 to-indigo-800/85 text-white"
            : `studio-chat-bubble--agent ${pinned ? "ring-1 ring-amber-400/50" : ""}`
        }`}
      >
        <div className="studio-chat-bubble-meta">
          <span className="min-w-0 truncate">{isUser ? "You" : "Design Agent"}</span>
          <span className="flex shrink-0 items-center gap-2 normal-case">
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
          <div className="space-y-2.5">
            {previewTarget ? <PreviewTargetActionCard target={previewTarget} /> : null}
            {userText ? (
              <div className="break-words whitespace-pre-wrap [overflow-wrap:anywhere]">{userText}</div>
            ) : null}
            {!previewTarget && !userText ? (
              <div className="text-white/70 italic">(message)</div>
            ) : null}
          </div>
        ) : (
          <div
            className="studio-chat-markdown prose-invert min-w-0 max-w-full break-words text-white/90 [overflow-wrap:anywhere] [&_.md-code]:break-all [&_.md-code]:rounded [&_.md-code]:bg-black/30 [&_.md-code]:px-1 [&_.md-pre]:mt-2 [&_.md-pre]:max-w-full [&_.md-pre]:overflow-x-auto [&_.md-pre]:rounded-lg [&_.md-pre]:bg-black/40 [&_.md-pre]:p-2 [&_.md-pre]:text-[11px] [&_.md-pre]:leading-snug [&_.md-pre]:whitespace-pre-wrap"
            dangerouslySetInnerHTML={{ __html: body }}
          />
        )}
      </div>
    </div>
  );
}
