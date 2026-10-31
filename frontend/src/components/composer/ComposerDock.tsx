import { FormEvent, useRef } from "react";
import { motion } from "framer-motion";
import BottomTriangleToggle from "./BottomTriangleToggle";

type Props = {
  open: boolean;
  onToggle: () => void;
  onSend: (text: string) => void;
  onUpload: (files: FileList) => void;
};

/** Fixed bottom dock — centered with flex (avoids Framer transform breaking translate-x centering). */
export default function ComposerDock({ open, onToggle, onSend, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const value = inputRef.current?.value.trim();
    if (value) {
      onSend(value);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-50 flex flex-col items-center pointer-events-none pb-4"
      aria-label="Message composer"
    >
      <div className="pointer-events-auto mb-1">
        <BottomTriangleToggle open={open} onToggle={onToggle} />
      </div>
      {open && (
        <motion.form
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={handleSubmit}
          className="pointer-events-auto w-[min(640px,calc(100vw-2rem))] flex gap-2 p-3 rounded-2xl bg-white/10 backdrop-blur border border-white/10 shadow-lg mx-auto"
        >
          <button
            type="button"
            className="px-3 rounded-xl bg-white/10 shrink-0"
            onClick={() => fileRef.current?.click()}
          >
            +
          </button>
          <input
            ref={inputRef}
            className="flex-1 min-w-0 bg-transparent outline-none text-sm"
            placeholder="Type your RFP details…"
          />
          <button type="submit" className="px-4 py-1 rounded-xl bg-cyan-500/80 text-sm shrink-0">
            Send
          </button>
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
