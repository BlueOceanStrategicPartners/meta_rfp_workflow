import { motion } from "framer-motion";

type Props = { open: boolean; onToggle: () => void };

export default function BottomTriangleToggle({ open, onToggle }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="text-cyan-300/80 hover:text-cyan-200"
      aria-label="Toggle composer"
    >
      <motion.div
        animate={{ rotate: open ? 180 : 0 }}
        className="w-0 h-0 border-l-[10px] border-r-[10px] border-b-[14px] border-l-transparent border-r-transparent border-b-current"
      />
    </button>
  );
}
