import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { CardSaveState } from "../../hooks/useDebouncedCardPatch";
import {
  amberSet,
  cardsToFormState,
  formStateToPatch,
  type RfpCardFormState,
} from "../../lib/rfpCardPatch";
import { useDebouncedCardPatch } from "../../hooks/useDebouncedCardPatch";

import type { ClientSessionState } from "../../lib/clientSession";
import { sessionNeedsMeetingSpace } from "../../lib/rfpFlow";
import ClientSessionTimeline from "./ClientSessionTimeline";
import CustomScrollArea from "../ui/CustomScrollArea";
import ClientSelect from "../ui/ClientSelect";

type Props = {
  cards: Record<string, unknown>;
  clientSession?: ClientSessionState;
  saveState?: CardSaveState;
  cardError?: string | null;
  onPatch: (patch: Record<string, unknown>) => void;
  onMarkSaving?: () => void;
};

function focusIdForClarification(label: string): string | null {
  const lower = label.toLowerCase();
  if (lower.includes("check-in")) return "check-in";
  if (lower.includes("check-out")) return "check-out";
  if (lower.includes("room night")) return "room-nights";
  if (lower.includes("headcount")) return "headcount";
  return null;
}

function focusFieldById(id: string) {
  const el = document.getElementById(id);
  if (el instanceof HTMLElement) {
    el.focus();
    el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

const SEATING = ["classroom", "theater", "banquet", "u-shape", "boardroom"] as const;

function formatUsd(value: unknown) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(
    n,
  );
}

export default function AgentCardDeck({
  cards,
  clientSession,
  saveState = "idle",
  cardError = null,
  onPatch,
  onMarkSaving,
}: Props) {
  const [form, setForm] = useState<RfpCardFormState>(() => cardsToFormState(cards));
  const baselineRef = useRef<RfpCardFormState>(cardsToFormState(cards));
  const cardsFingerprint = useMemo(() => JSON.stringify(cards), [cards]);

  useEffect(() => {
    const next = cardsToFormState(cards);
    baselineRef.current = next;
    setForm(next);
  }, [cardsFingerprint, cards]);

  const submitPatch = useCallback(
    (patch: Record<string, unknown>) => {
      onMarkSaving?.();
      onPatch(patch);
    },
    [onMarkSaving, onPatch],
  );

  const { queuePatch } = useDebouncedCardPatch(submitPatch);

  const updateField = useCallback(
    (key: keyof RfpCardFormState, value: string) => {
      setForm((prev) => {
        const next = { ...prev, [key]: value };
        const patch = formStateToPatch(baselineRef.current, next);
        if (patch) queuePatch(patch);
        return next;
      });
    },
    [queuePatch],
  );

  const overview = (cards.event_overview as Record<string, unknown>) || {};
  const quote = (cards.live_quote as Record<string, unknown>) || {};
  const amberOverview = amberSet(cards, "event_overview");
  const amberRoom = amberSet(cards, "room_block");

  const clarifications = clientSession?.clarification_options || [];
  const todos = clientSession?.agent_todos || [];
  const showMeetingCards = sessionNeedsMeetingSpace(clientSession, cards);

  return (
    <motion.aside
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, ease: [0.45, 0.05, 0.25, 1] }}
      className="client-side-deck pointer-events-auto fixed right-3 top-[4.75rem] bottom-0 z-30 flex w-[min(20rem,calc(100vw-1.5rem))] flex-col overflow-hidden sm:right-4 sm:w-80"
      aria-label="RFP summary cards"
    >
      <div className="client-side-deck__header flex shrink-0 items-center justify-between gap-2 px-1 pb-2">
        <h2 className="client-side-deck__title text-sm font-semibold tracking-tight">Your RFP summary</h2>
        <SaveIndicator state={saveState} />
      </div>

      {cardError && (
        <div className="client-side-card client-side-card--error mb-2 shrink-0 px-3 py-2.5" role="alert">
          <p className="text-xs leading-snug">{cardError}</p>
        </div>
      )}

      <AnimatePresence mode="popLayout">
        <motion.div
          key={String(quote.anchor_price || "empty")}
          layout
          initial={{ opacity: 0.6, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="client-side-live-estimate client-side-card client-side-card--quote mb-2 shrink-0 px-3 py-3"
        >
          <p className="client-side-card__kicker">Live estimate</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight">{formatUsd(quote.anchor_price)}</p>
          <p className="client-side-field-hint mt-1 text-[11px]">Updates automatically when you edit the cards.</p>
        </motion.div>
      </AnimatePresence>

      <div className="client-side-deck-scroll-shell relative min-h-0 flex-1 overflow-hidden">
        <div className="client-side-deck-scroll-fade client-side-deck-scroll-fade--top" aria-hidden />
        <div className="client-side-deck-scroll-fade client-side-deck-scroll-fade--bottom" aria-hidden />
        <CustomScrollArea
          className="absolute inset-0"
          contentClassName="flex flex-col gap-2 pb-3 pl-0.5 pr-3"
        >
      {(clarifications.length > 0 || todos.some((t) => t.status === "pending")) && (
        <motion.div layout className="client-side-card client-side-card--alert px-3 py-2.5">
          <p className="client-side-card__kicker mb-1.5">Needs your input</p>
          <ul className="space-y-1 text-xs">
            {todos
              .filter((t) => t.status === "pending")
              .map((t) => (
                <li key={t.id} className="client-side-todo flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" aria-hidden />
                  {t.text}
                </li>
              ))}
          </ul>
          {clarifications.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {clarifications.map((c) => (
                <button
                  key={c}
                  type="button"
                  className="client-side-clarify-chip rounded-full px-2 py-0.5 text-[10px] transition hover:brightness-110"
                  onClick={() => {
                    const id = focusIdForClarification(c);
                    if (id) focusFieldById(id);
                  }}
                >
                  {c}
                </button>
              ))}
            </div>
          )}
        </motion.div>
      )}

      <SideCard title="Event overview" amber={amberOverview.size > 0} delay={0.05}>
        <p className="client-side-field-value text-sm font-medium">{String(overview.company_name || "—")}</p>
        <p className="client-side-field-hint text-xs">{String(overview.event_type || "Event")}</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Field
            id="check-in"
            label="Check-in"
            type="date"
            value={form.checkIn}
            amber={amberOverview.has("check_in_date")}
            onChange={(v) => updateField("checkIn", v)}
          />
          <Field
            id="check-out"
            label="Check-out"
            type="date"
            value={form.checkOut}
            amber={amberOverview.has("check_out_date")}
            onChange={(v) => updateField("checkOut", v)}
          />
        </div>
      </SideCard>

      <SideCard title="Room block" amber={amberRoom.size > 0} delay={0.1}>
        <div className="grid grid-cols-2 gap-2">
          <Field
            id="room-nights"
            label="Room nights"
            type="number"
            min={0}
            value={form.totalRoomNights}
            amber={amberRoom.has("total_room_nights")}
            onChange={(v) => updateField("totalRoomNights", v)}
          />
          <Field
            label="Peak rooms"
            type="number"
            min={0}
            value={form.peakRooms}
            onChange={(v) => updateField("peakRooms", v)}
          />
        </div>
      </SideCard>

      {showMeetingCards ? (
        <>
      <SideCard title="Meeting space" delay={0.15}>
        <Field
          id="headcount"
          label="Headcount"
          type="number"
          min={0}
          value={form.headcount}
          onChange={(v) => updateField("headcount", v)}
        />
        <ClientSelect
          id="seating-style"
          className="client-side-field mt-2"
          label="Seating style"
          value={form.seatingStyle}
          onChange={(v) => updateField("seatingStyle", v)}
          options={SEATING.map((s) => ({ value: s, label: s.replace("-", " ") }))}
        />
      </SideCard>

      <SideCard title="Catering & AV" delay={0.2}>
        <TextAreaField
          label="Catering notes"
          value={form.cateringNotes}
          onChange={(v) => updateField("cateringNotes", v)}
        />
        <TextAreaField
          label="AV specs"
          value={form.avSpecs}
          onChange={(v) => updateField("avSpecs", v)}
          className="mt-2"
        />
      </SideCard>
        </>
      ) : null}

      <ClientSessionTimeline session={clientSession} />
        </CustomScrollArea>
      </div>
    </motion.aside>
  );
}

function SaveIndicator({ state }: { state: CardSaveState }) {
  if (state === "idle") return null;
  const label =
    state === "saving" ? "Saving…" : state === "saved" ? "Saved" : state === "error" ? "Couldn’t save" : "";
  return (
    <span
      className={`client-side-save text-[10px] font-medium uppercase tracking-wide ${
        state === "error" ? "client-side-save--error" : state === "saved" ? "client-side-save--ok" : ""
      }`}
    >
      {label}
    </span>
  );
}

function SideCard({
  title,
  children,
  amber,
  delay = 0,
}: {
  title: string;
  children: ReactNode;
  amber?: boolean;
  delay?: number;
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.45, 0.05, 0.25, 1] }}
      className={`client-side-card px-3 py-3 ${amber ? "client-side-card--amber" : ""}`}
    >
      <h3 className="client-side-card__title mb-2 text-sm font-medium">{title}</h3>
      {children}
    </motion.div>
  );
}

function TextAreaField({
  label,
  value,
  onChange,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <label className={`client-side-field block ${className}`}>
      <span className="client-side-field-label">{label}</span>
      <textarea
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="client-side-input client-side-textarea mt-1 w-full min-h-[4.5rem] resize-y"
      />
    </label>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  amber,
  type = "text",
  min,
  className = "",
}: {
  id?: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  amber?: boolean;
  type?: string;
  min?: number;
  className?: string;
}) {
  return (
    <label className={`client-side-field block ${className}`}>
      <span className="client-side-field-label">{label}</span>
      <input
        id={id}
        type={type}
        min={min}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`client-side-input mt-1 w-full ${amber ? "client-side-input--amber" : ""}`}
      />
    </label>
  );
}
