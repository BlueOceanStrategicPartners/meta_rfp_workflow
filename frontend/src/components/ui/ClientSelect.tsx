import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useRef, useState } from "react";

export type ClientSelectOption = {
  value: string;
  label: string;
};

type Props = {
  id?: string;
  label: string;
  value: string;
  options: ClientSelectOption[];
  onChange: (value: string) => void;
  amber?: boolean;
  className?: string;
  disabled?: boolean;
};

function ChevronDown({ open }: { open: boolean }) {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
      className={`shrink-0 opacity-70 transition-transform ${open ? "rotate-180" : ""}`}
    >
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Custom listbox — matches client-side inputs (no native OS select popup). */
export default function ClientSelect({
  id,
  label,
  value,
  options,
  onChange,
  amber,
  className = "",
  disabled,
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();
  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const onDocMouse = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onDocKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocMouse);
    document.addEventListener("keydown", onDocKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouse);
      document.removeEventListener("keydown", onDocKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={`client-side-select relative block ${className}`.trim()}>
      <span className="client-side-field-label">{label}</span>
      <button
        id={id}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        className={`client-side-select__trigger client-side-input mt-1 flex w-full items-center justify-between gap-2 text-left ${
          amber ? "client-side-input--amber" : ""
        } ${open ? "client-side-select__trigger--open" : ""}`}
        onClick={() => !disabled && setOpen((v) => !v)}
      >
        <span className="min-w-0 truncate">{selected?.label ?? value}</span>
        <ChevronDown open={open} />
      </button>
      <AnimatePresence>
        {open ? (
          <motion.ul
            id={listId}
            role="listbox"
            aria-label={label}
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.16, ease: [0.45, 0.05, 0.25, 1] }}
            className="client-side-select__menu"
          >
            {options.map((opt) => {
              const active = opt.value === value;
              return (
                <li key={opt.value} role="presentation">
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    className={`client-side-select__option ${active ? "client-side-select__option--active" : ""}`}
                    onClick={() => {
                      onChange(opt.value);
                      setOpen(false);
                    }}
                  >
                    {opt.label}
                  </button>
                </li>
              );
            })}
          </motion.ul>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
