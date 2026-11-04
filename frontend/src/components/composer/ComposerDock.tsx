import { FormEvent, ReactNode, useRef, useState } from "react";
import { motion } from "framer-motion";
import BottomTriangleToggle from "./BottomTriangleToggle";

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
  proposalMode?: boolean;
  onBackFromProposal?: () => void;
  leadingSlot?: ReactNode;
};

const COMPOSER_PANEL =
  "client-composer-panel pointer-events-auto mx-auto flex w-[min(640px,calc(100vw-2rem))] items-center gap-2 rounded-full py-2 pl-3 pr-3.5 shadow-lg backdrop-blur sm:py-2.5 sm:pl-3.5 sm:pr-4";

/** Fixed bottom dock — same pill composer in intake and proposal (proposal adds back + mini orb). */
export default function ComposerDock({
  open,
  onToggle,
  onSend,
  onUpload,
  proposalMode = false,
  onBackFromProposal,
  leadingSlot,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [hasText, setHasText] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const value = inputRef.current?.value.trim();
    if (value) {
      onSend(value);
      if (inputRef.current) {
        inputRef.current.value = "";
        setHasText(false);
      }
    }
  };

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-50 flex flex-col items-center pointer-events-none pb-[max(0.5rem,env(safe-area-inset-bottom))]"
      aria-label="Message composer"
    >
      {!proposalMode && (
        <div className="pointer-events-auto mb-1">
          <BottomTriangleToggle open={open} onToggle={onToggle} />
        </div>
      )}
      {(open || proposalMode) && (
        <motion.form
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={handleSubmit}
          className={COMPOSER_PANEL}
        >
          {proposalMode && onBackFromProposal ? (
            <motion.button
              type="button"
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              className="client-composer-back flex h-10 shrink-0 items-center justify-center rounded-full px-3.5 text-xs font-medium"
              aria-label="Back to summary cards"
              onClick={onBackFromProposal}
            >
              Back
            </motion.button>
          ) : null}
          {leadingSlot}
          {!proposalMode && (
            <motion.button
              type="button"
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              className="client-composer-attach flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg leading-none"
              aria-label="Attach files"
              onClick={() => fileRef.current?.click()}
            >
              +
            </motion.button>
          )}
          <input
            ref={inputRef}
            className="client-composer-input min-h-10 flex-1 min-w-0 bg-transparent px-1 text-sm outline-none"
            placeholder={proposalMode ? "Ask about your proposal…" : "Type your RFP details…"}
            onChange={(e) => setHasText(e.target.value.trim().length > 0)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
          />
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
