import { FormEvent, ReactNode, useRef, useState } from "react";
import { motion } from "framer-motion";
import BottomTriangleToggle from "./BottomTriangleToggle";
import ComposerMultilineField, { resetComposerField } from "./ComposerMultilineField";
import ComposerTooltip from "./ComposerTooltip";
import { IconComposerBack, IconComposerPlus, IconComposerProposal, IconComposerUpload } from "./ClientComposerIcons";

const ICON_BTN_SPRING = { type: "spring" as const, stiffness: 520, damping: 28 };

function IconSend() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" aria-hidden className="shrink-0">
      <path
        d="M3.4 20.4 21 12 3.4 3.6l1.8 7.2L16 12l-10.8 1.2 1.8 7.2z"
        fill="currentColor"
      />
    </svg>
  );
}

type Props = {
  open: boolean;
  onToggle: () => void;
  onSend: (text: string) => void;
  onUpload: (files: FileList) => void;
  onNewSession?: () => void;
  proposalMode?: boolean;
  onBackFromProposal?: () => void;
  showOpenProposal?: boolean;
  onOpenProposal?: () => void;
  leadingSlot?: ReactNode;
};

const COMPOSER_PANEL_BASE =
  "client-composer-panel pointer-events-auto mx-auto flex w-[min(640px,calc(100vw-2rem))] items-end gap-2 overflow-visible rounded-[1.625rem] py-2 pl-3 pr-3.5 shadow-lg sm:py-2.5 sm:pl-3.5 sm:pr-4";

/** Fixed bottom dock — same pill composer in intake and proposal (proposal adds back + mini orb). */
export default function ComposerDock({
  open,
  onToggle,
  onSend,
  onUpload,
  onNewSession,
  proposalMode = false,
  onBackFromProposal,
  showOpenProposal = false,
  onOpenProposal,
  leadingSlot,
}: Props) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [hasText, setHasText] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const el = inputRef.current;
    const value = el?.value.trim();
    if (value && el) {
      onSend(value);
      resetComposerField(el);
      setHasText(false);
    }
  };

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-50 flex flex-col items-center pointer-events-none pb-[max(0.5rem,env(safe-area-inset-bottom))]"
      aria-label="Message composer"
    >
      {!proposalMode && (
        <div className="pointer-events-auto mb-1">
          <ComposerTooltip label={open ? "Hide composer" : "Show composer"} placement="bottom">
            <BottomTriangleToggle open={open} onToggle={onToggle} />
          </ComposerTooltip>
        </div>
      )}
      {(open || proposalMode) && (
        <motion.form
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={handleSubmit}
          className={`${COMPOSER_PANEL_BASE}${proposalMode ? " client-composer-panel--proposal" : " backdrop-blur"}`}
        >
          {proposalMode && onBackFromProposal ? (
            <ComposerTooltip label="Back to summary cards">
              <motion.button
                type="button"
                whileHover={{ scale: 1.06, x: -2 }}
                whileTap={{ scale: 0.94, x: 0 }}
                transition={ICON_BTN_SPRING}
                className="client-composer-back client-composer-icon-btn shrink-0"
                aria-label="Back to summary cards"
                onClick={onBackFromProposal}
              >
                <motion.span
                  className="flex items-center justify-center"
                  whileHover={{ x: -1 }}
                  transition={ICON_BTN_SPRING}
                >
                  <IconComposerBack />
                </motion.span>
              </motion.button>
            </ComposerTooltip>
          ) : null}
          {leadingSlot}
          {!proposalMode && showOpenProposal && onOpenProposal ? (
            <ComposerTooltip label="Open proposal">
              <motion.button
                type="button"
                whileHover={{ scale: 1.06 }}
                whileTap={{ scale: 0.94 }}
                transition={ICON_BTN_SPRING}
                className="client-composer-proposal-open flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-full pl-2.5 pr-3 text-[11px] font-semibold uppercase tracking-wide"
                aria-label="Open proposal"
                onClick={onOpenProposal}
              >
                <IconComposerProposal />
                <span>Proposal</span>
              </motion.button>
            </ComposerTooltip>
          ) : null}
          {!proposalMode && onNewSession ? (
            <ComposerTooltip label="New session">
              <motion.button
                type="button"
                whileHover={{ scale: 1.06 }}
                whileTap={{ scale: 0.94 }}
                transition={ICON_BTN_SPRING}
                className="client-composer-attach client-composer-icon-btn shrink-0"
                aria-label="Start new RFP session"
                onClick={onNewSession}
              >
                <IconComposerPlus />
              </motion.button>
            </ComposerTooltip>
          ) : null}
          {!proposalMode && (
            <ComposerTooltip label="Upload RFP file">
              <motion.button
                type="button"
                whileHover={{ scale: 1.06 }}
                whileTap={{ scale: 0.94 }}
                transition={ICON_BTN_SPRING}
                className="client-composer-upload client-composer-icon-btn shrink-0"
                aria-label="Upload RFP document"
                onClick={() => fileRef.current?.click()}
              >
                <IconComposerUpload />
              </motion.button>
            </ComposerTooltip>
          )}
          <ComposerMultilineField
            ref={inputRef}
            placeholder={proposalMode ? "Ask about your proposal…" : "Type your RFP details…"}
            aria-label={proposalMode ? "Ask about your proposal" : "Type your RFP details"}
            onValueChange={(value) => setHasText(value.trim().length > 0)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <ComposerTooltip label={hasText ? "Send message" : "Type a message to send"}>
            <motion.button
              type="submit"
              disabled={!hasText}
              aria-label="Send message"
              className="client-composer-send group relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full disabled:cursor-not-allowed disabled:opacity-45"
              whileHover={hasText ? { scale: 1.04, y: -1 } : undefined}
              whileTap={hasText ? { scale: 0.94 } : undefined}
              transition={{ type: "spring", stiffness: 520, damping: 28 }}
            >
              <span className="client-composer-send__shine pointer-events-none absolute inset-0 opacity-0 transition-opacity group-hover:opacity-100 group-disabled:opacity-0" aria-hidden />
              <motion.span
                className="relative flex items-center justify-center text-white"
                animate={hasText ? { x: 0, opacity: 1 } : { x: 0, opacity: 0.85 }}
              >
                <IconSend />
              </motion.span>
            </motion.button>
          </ComposerTooltip>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.xlsx"
            className="hidden"
            onChange={(e) => e.target.files && onUpload(e.target.files)}
          />
        </motion.form>
      )}
    </div>
  );
}
