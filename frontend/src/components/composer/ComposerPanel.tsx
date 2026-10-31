import { FormEvent, useRef } from "react";
import { motion } from "framer-motion";

type Props = {
  open: boolean;
  onSend: (text: string) => void;
  onUpload: (files: FileList) => void;
};

export default function ComposerPanel({ open, onSend, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const value = inputRef.current?.value.trim();
    if (value) {
      onSend(value);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <motion.form
      initial={{ y: 40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      onSubmit={handleSubmit}
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-[min(640px,90vw)] flex gap-2 p-3 rounded-2xl bg-white/10 backdrop-blur border border-white/10 shadow-lg"
    >
      <button
        type="button"
        className="px-3 rounded-xl bg-white/10"
        onClick={() => fileRef.current?.click()}
      >
        +
      </button>
      <input
        ref={inputRef}
        className="flex-1 bg-transparent outline-none text-sm"
        placeholder="Type your RFP details..."
      />
      <button type="submit" className="px-4 py-1 rounded-xl bg-cyan-500/80 text-sm">
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
  );
}
