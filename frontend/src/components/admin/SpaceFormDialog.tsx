import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  AdminApiError,
  createSpace,
  errorMessage,
  fieldError,
  updateSpace,
  type Capacities,
  type Space,
  type SpaceInput,
} from "../../lib/adminApi";
import { SPACE_TYPES, spaceTypeLabel } from "../../lib/adminFormat";

const CAPACITY_KEYS: { key: keyof Capacities; label: string }[] = [
  { key: "banquet", label: "Banquet" },
  { key: "classroom", label: "Classroom" },
  { key: "theater", label: "Theater" },
  { key: "u_shape", label: "U-shape" },
  { key: "cocktail", label: "Cocktail" },
];

type FormState = {
  name: string;
  space_type: string;
  capacities: Record<keyof Capacities, string>;
  rack_rate: string;
  base_floor_cost: string;
  av: string;
};

function initialState(space?: Space | null): FormState {
  const caps = space?.capacities_json ?? {};
  const av = Array.isArray(space?.av_capabilities_json)
    ? (space!.av_capabilities_json as unknown[]).map(String).join(", ")
    : "";
  return {
    name: space?.name ?? "",
    space_type: space?.space_type ?? "BALLROOM",
    capacities: {
      banquet: caps.banquet != null ? String(caps.banquet) : "",
      classroom: caps.classroom != null ? String(caps.classroom) : "",
      theater: caps.theater != null ? String(caps.theater) : "",
      u_shape: caps.u_shape != null ? String(caps.u_shape) : "",
      cocktail: caps.cocktail != null ? String(caps.cocktail) : "",
    },
    rack_rate: space?.rack_rate != null ? String(Number(space.rack_rate)) : "",
    base_floor_cost: space?.base_floor_cost != null ? String(Number(space.base_floor_cost)) : "",
    av,
  };
}

type Errors = Partial<Record<string, string>>;

function validate(f: FormState): Errors {
  const e: Errors = {};
  if (!f.name.trim()) e.name = "Give the space a name.";
  for (const { key } of CAPACITY_KEYS) {
    const raw = f.capacities[key].trim();
    if (raw === "") continue;
    const n = Number(raw);
    if (!Number.isInteger(n) || n < 0) e[`cap_${key}`] = "Whole number, 0 or more.";
  }
  const rack = Number(f.rack_rate);
  if (f.rack_rate.trim() === "" || !Number.isFinite(rack) || rack < 0) e.rack_rate = "Enter a price of 0 or more.";
  const floor = Number(f.base_floor_cost);
  if (f.base_floor_cost.trim() === "" || !Number.isFinite(floor) || floor < 0) {
    e.base_floor_cost = "Enter a cost of 0 or more.";
  } else if (!e.rack_rate && floor > rack) {
    e.base_floor_cost = "Floor cost can't be higher than the rack rate.";
  }
  return e;
}

type Props = {
  open: boolean;
  propertyId: string;
  /** Edit this space; omit to create a new one. */
  space?: Space | null;
  onClose: () => void;
  onSaved: (space: Space, created: boolean) => void;
};

export default function SpaceFormDialog({ open, propertyId, space, onClose, onSaved }: Props) {
  const [form, setForm] = useState<FormState>(() => initialState(space));
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [serverFieldErrors, setServerFieldErrors] = useState<Errors>({});
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const editing = !!space;
  // Only offer the AV editor when the stored value is a simple list (or empty).
  const avEditable = !space || space.av_capabilities_json == null || Array.isArray(space.av_capabilities_json);

  useEffect(() => {
    if (!open) return;
    setForm(initialState(space));
    setTouched(false);
    setServerError(null);
    setServerFieldErrors({});
    window.setTimeout(() => firstFieldRef.current?.focus(), 0);
  }, [open, space]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onClose]);

  const errors = useMemo(() => validate(form), [form]);
  const valid = Object.keys(errors).length === 0;
  const errFor = (key: string) => (touched ? errors[key] : undefined) ?? serverFieldErrors[key];

  if (!open) return null;

  const setCap = (key: keyof Capacities, value: string) =>
    setForm((f) => ({ ...f, capacities: { ...f.capacities, [key]: value } }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!valid || busy) return;
    setBusy(true);
    setServerError(null);
    setServerFieldErrors({});
    // Blank seating styles are left out (the space doesn't offer that layout).
    const capacities: Capacities = {};
    for (const { key } of CAPACITY_KEYS) {
      const raw = form.capacities[key].trim();
      if (raw !== "") capacities[key] = Number(raw);
    }
    const body: SpaceInput = {
      property: propertyId,
      name: form.name.trim(),
      space_type: form.space_type,
      capacities_json: capacities,
      rack_rate: Number(form.rack_rate).toFixed(2),
      base_floor_cost: Number(form.base_floor_cost).toFixed(2),
    };
    if (avEditable) {
      body.av_capabilities_json = form.av
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    try {
      const saved = editing ? await updateSpace(space!.id, body) : await createSpace(body);
      onSaved(saved, !editing);
    } catch (err) {
      if (err instanceof AdminApiError && err.errors) {
        const fe: Errors = {};
        for (const k of ["name", "space_type", "rack_rate", "base_floor_cost", "capacities_json", "av_capabilities_json"]) {
          const msg = fieldError(err.errors, k);
          if (msg) fe[k] = msg;
        }
        setServerFieldErrors(fe);
      }
      setServerError(errorMessage(err, "We couldn't save this space."));
    } finally {
      setBusy(false);
    }
  };

  const title = editing ? `Edit ${space!.name}` : "Add a space";

  return (
    <div className="admin-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="space-form-title">
      <form className="admin-modal" onSubmit={(e) => void submit(e)} noValidate>
        <header className="studio-panel-header !min-h-0">
          <div>
            <p className="studio-panel-kicker">Inventory</p>
            <h3 id="space-form-title" className="text-lg font-semibold">
              {title}
            </h3>
          </div>
        </header>
        <div className="studio-panel-body studio-scroll min-h-0 flex-1 space-y-4 overflow-y-auto !pt-5">
          {serverError ? (
            <p className="admin-alert" role="alert">
              {serverError}
            </p>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="admin-label">Name</span>
              <input
                ref={firstFieldRef}
                className={`studio-field ${errFor("name") ? "admin-field-invalid" : ""}`}
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Grand Ballroom"
                aria-invalid={!!errFor("name")}
              />
              {errFor("name") ? <span className="admin-danger-text mt-1 block text-xs">{errFor("name")}</span> : null}
            </label>
            <label className="block">
              <span className="admin-label">Type</span>
              <select
                className="studio-field"
                value={form.space_type}
                onChange={(e) => setForm((f) => ({ ...f, space_type: e.target.value }))}
              >
                {SPACE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {spaceTypeLabel(t)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <fieldset>
            <legend className="admin-label">Capacity (people) by seating style</legend>
            <p className="admin-faint -mt-1 mb-2 text-[11px]">Leave a layout blank if the space doesn't offer it.</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {CAPACITY_KEYS.map(({ key, label }) => (
                <label key={key} className="block min-w-0">
                  <span className="admin-muted mb-1 block text-[11px]">{label}</span>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    inputMode="numeric"
                    className={`studio-field admin-num !px-2.5 text-right ${errFor(`cap_${key}`) ? "admin-field-invalid" : ""}`}
                    value={form.capacities[key]}
                    onChange={(e) => setCap(key, e.target.value)}
                    placeholder="—"
                    aria-invalid={!!errFor(`cap_${key}`)}
                  />
                  {errFor(`cap_${key}`) ? (
                    <span className="admin-danger-text mt-1 block text-[11px]">{errFor(`cap_${key}`)}</span>
                  ) : null}
                </label>
              ))}
            </div>
            {serverFieldErrors.capacities_json ? (
              <span className="admin-danger-text mt-1 block text-xs">{serverFieldErrors.capacities_json}</span>
            ) : null}
          </fieldset>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="admin-label">Rack rate (per night)</span>
              <input
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                className={`studio-field admin-num ${errFor("rack_rate") ? "admin-field-invalid" : ""}`}
                value={form.rack_rate}
                onChange={(e) => setForm((f) => ({ ...f, rack_rate: e.target.value }))}
                aria-invalid={!!errFor("rack_rate")}
              />
              {errFor("rack_rate") ? (
                <span className="admin-danger-text mt-1 block text-xs">{errFor("rack_rate")}</span>
              ) : null}
            </label>
            <label className="block">
              <span className="admin-label">Floor cost (per night)</span>
              <input
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                className={`studio-field admin-num ${errFor("base_floor_cost") ? "admin-field-invalid" : ""}`}
                value={form.base_floor_cost}
                onChange={(e) => setForm((f) => ({ ...f, base_floor_cost: e.target.value }))}
                aria-invalid={!!errFor("base_floor_cost")}
              />
              {errFor("base_floor_cost") ? (
                <span className="admin-danger-text mt-1 block text-xs">{errFor("base_floor_cost")}</span>
              ) : (
                <span className="admin-faint mt-1 block text-[11px]">Must be at or below the rack rate.</span>
              )}
            </label>
          </div>

          {avEditable ? (
            <label className="block">
              <span className="admin-label">AV equipment</span>
              <input
                className="studio-field"
                value={form.av}
                onChange={(e) => setForm((f) => ({ ...f, av: e.target.value }))}
                placeholder="Projector, PA system, Stage lighting"
              />
              <span className="admin-faint mt-1 block text-[11px]">Separate items with commas.</span>
            </label>
          ) : null}
        </div>
        <footer className="studio-panel-footer flex flex-wrap justify-end gap-2">
          <button type="button" className="studio-btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="submit"
            className="studio-btn-secondary admin-btn-primary"
            disabled={busy || (touched && !valid)}
          >
            {busy ? "Saving…" : editing ? "Save space" : "Add space"}
          </button>
        </footer>
      </form>
    </div>
  );
}
