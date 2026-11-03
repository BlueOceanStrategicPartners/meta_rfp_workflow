import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import AdminConfirm from "../../components/admin/AdminConfirm";
import AdminPanel from "../../components/admin/AdminPanel";
import AdminTable, { type AdminColumn } from "../../components/admin/AdminTable";
import { IconEdit, IconPlus, IconRefresh, IconTrashAdmin, IconUnlock } from "../../components/admin/AdminIcons";
import { useAdminFeedback } from "../../components/admin/AdminLayout";
import LoadState from "../../components/admin/LoadState";
import SpaceFormDialog from "../../components/admin/SpaceFormDialog";
import { Chip } from "../../components/admin/StatusChip";
import { usePolling } from "../../hooks/usePolling";
import {
  createProperty,
  deleteProperty,
  deleteSpace,
  errorMessage,
  listProperties,
  listSpaces,
  releaseSpace,
  updateProperty,
  type Property,
  type Space,
} from "../../lib/adminApi";
import { EMPTY, formatMoney, spaceTypeLabel } from "../../lib/adminFormat";
import { useAdminProperty } from "../../hooks/useAdminProperty";

/* ---------------- Property dialog ---------------- */

function defaultTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

function PropertyDialog({
  open,
  property,
  onClose,
  onSaved,
}: {
  open: boolean;
  property: Property | null;
  onClose: () => void;
  onSaved: (p: Property, created: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setName(property?.name ?? "");
    setTimezone(property?.timezone ?? defaultTimezone());
    setError(null);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open, property]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onClose]);

  if (!open) return null;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const body = { name: name.trim(), timezone: timezone.trim() || "UTC" };
      const saved = property ? await updateProperty(property.id, body) : await createProperty(body);
      onSaved(saved, !property);
    } catch (err) {
      setError(errorMessage(err, "We couldn't save the property."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="admin-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="property-form-title">
      <form className="admin-modal !max-w-md" onSubmit={(e) => void submit(e)} noValidate>
        <header className="studio-panel-header !min-h-0">
          <div>
            <p className="studio-panel-kicker">Inventory</p>
            <h3 id="property-form-title" className="text-lg font-semibold">
              {property ? "Rename property" : "Add a property"}
            </h3>
          </div>
        </header>
        <div className="studio-panel-body space-y-3 !pt-5">
          {error ? (
            <p className="admin-alert" role="alert">
              {error}
            </p>
          ) : null}
          <label className="block">
            <span className="admin-label">Name</span>
            <input
              ref={inputRef}
              className="studio-field"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Harbour View Hotel"
            />
          </label>
          <label className="block">
            <span className="admin-label">Time zone</span>
            <input
              className="studio-field"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="e.g. Asia/Colombo"
            />
          </label>
        </div>
        <footer className="studio-panel-footer flex justify-end gap-2">
          <button type="button" className="studio-btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="studio-btn-secondary admin-btn-primary" disabled={busy || !name.trim()}>
            {busy ? "Saving…" : property ? "Save name" : "Add property"}
          </button>
        </footer>
      </form>
    </div>
  );
}

/* ---------------- Page ---------------- */

type PendingAction =
  | { kind: "delete-space"; space: Space }
  | { kind: "release"; space: Space }
  | { kind: "delete-property"; property: Property };

export default function InventoryPage() {
  const { notify } = useAdminFeedback();
  const propsQ = usePolling(listProperties, 0);
  const [propertyId, setPropertyId] = useAdminProperty(propsQ.data);
  const property = propsQ.data?.find((p) => p.id === propertyId) ?? null;

  const spacesQ = usePolling(
    () => (propertyId ? listSpaces({ property: propertyId }) : Promise.resolve([] as Space[])),
    0,
    [propertyId],
  );

  const [spaceDialog, setSpaceDialog] = useState<{ open: boolean; space: Space | null }>({ open: false, space: null });
  const [propertyDialog, setPropertyDialog] = useState<{ open: boolean; property: Property | null }>({
    open: false,
    property: null,
  });
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [busy, setBusy] = useState(false);

  const closeSpaceDialog = useCallback(() => setSpaceDialog({ open: false, space: null }), []);
  const closePropertyDialog = useCallback(() => setPropertyDialog({ open: false, property: null }), []);

  const runPending = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      if (pending.kind === "delete-space") {
        await deleteSpace(pending.space.id);
        notify(`${pending.space.name} deleted.`, "success");
      } else if (pending.kind === "release") {
        await releaseSpace(pending.space.id);
        notify(`Booking released. ${pending.space.name} is available again.`, "success");
      } else {
        await deleteProperty(pending.property.id);
        notify(`${pending.property.name} deleted.`, "success");
      }
      setPending(null);
      await Promise.all([spacesQ.reload(), propsQ.reload()]);
    } catch (err) {
      setPending(null);
      notify(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };

  const columns: AdminColumn<Space>[] = [
    {
      key: "name",
      header: "Name",
      render: (s) => <span className="block min-w-[9rem] font-medium">{s.name}</span>,
    },
    { key: "type", header: "Type", render: (s) => <span className="whitespace-nowrap">{spaceTypeLabel(s.space_type)}</span> },
    { key: "banquet", header: "Banquet", numeric: true, render: (s) => s.capacities_json?.banquet ?? EMPTY },
    { key: "classroom", header: "Classroom", numeric: true, render: (s) => s.capacities_json?.classroom ?? EMPTY },
    { key: "theater", header: "Theater", numeric: true, render: (s) => s.capacities_json?.theater ?? EMPTY },
    { key: "rack", header: "Rack rate", numeric: true, render: (s) => formatMoney(s.rack_rate) },
    { key: "floor", header: "Floor cost", numeric: true, render: (s) => formatMoney(s.base_floor_cost) },
    {
      key: "status",
      header: "Status",
      render: (s) => (s.is_booked ? <Chip tone="amber">Booked</Chip> : <Chip tone="green">Available</Chip>),
    },
    {
      key: "actions",
      header: <span className="admin-sr-only">Actions</span>,
      className: "text-right",
      render: (s) => (
        <span className="flex justify-end gap-1.5">
          <button
            type="button"
            className="studio-btn-secondary admin-btn-small"
            onClick={() => setSpaceDialog({ open: true, space: s })}
            aria-label={`Edit ${s.name}`}
          >
            <IconEdit />
            Edit
          </button>
          {s.is_booked ? (
            <button
              type="button"
              className="studio-btn-secondary admin-btn-small"
              onClick={() => setPending({ kind: "release", space: s })}
              aria-label={`Release booking for ${s.name}`}
            >
              <IconUnlock />
              Release booking
            </button>
          ) : null}
          <button
            type="button"
            className="studio-btn-secondary studio-btn-danger admin-btn-small"
            disabled={s.is_booked}
            title={s.is_booked ? "Release the booking before deleting." : undefined}
            onClick={() => setPending({ kind: "delete-space", space: s })}
            aria-label={`Delete ${s.name}`}
          >
            <IconTrashAdmin />
            Delete
          </button>
        </span>
      ),
    },
  ];

  const confirmCopy = (() => {
    if (!pending) return null;
    if (pending.kind === "delete-space") {
      return {
        title: `Delete ${pending.space.name}?`,
        message: "This removes the space from inventory. It can't be undone.",
        label: "Delete space",
      };
    }
    if (pending.kind === "release") {
      return {
        title: `Release the booking for ${pending.space.name}?`,
        message: "The space becomes available for new requests straight away.",
        label: "Release booking",
      };
    }
    return {
      title: `Delete ${pending.property.name}?`,
      message: "This removes the property. It can't be undone.",
      label: "Delete property",
    };
  })();

  const properties = propsQ.data ?? [];

  return (
    <AdminPanel
      kicker="Module 5 · Inventory"
      title="Venues and spaces"
      subtitle="The rooms and halls the agent can offer, with their capacities and prices."
      actions={
        <button
          type="button"
          className="studio-btn-secondary"
          onClick={() => {
            void propsQ.reload();
            void spacesQ.reload();
          }}
        >
          <IconRefresh />
          Refresh
        </button>
      }
    >
      {confirmCopy ? (
        <AdminConfirm
          open
          danger
          title={confirmCopy.title}
          message={confirmCopy.message}
          confirmLabel={confirmCopy.label}
          busyLabel="Working…"
          busy={busy}
          onConfirm={() => void runPending()}
          onCancel={() => setPending(null)}
        />
      ) : null}
      {propertyId ? (
        <SpaceFormDialog
          open={spaceDialog.open}
          propertyId={propertyId}
          space={spaceDialog.space}
          onClose={closeSpaceDialog}
          onSaved={(s, created) => {
            closeSpaceDialog();
            notify(created ? `${s.name} added.` : `${s.name} saved.`, "success");
            void spacesQ.reload();
            void propsQ.reload();
          }}
        />
      ) : null}
      <PropertyDialog
        open={propertyDialog.open}
        property={propertyDialog.property}
        onClose={closePropertyDialog}
        onSaved={(p, created) => {
          closePropertyDialog();
          notify(created ? `${p.name} added.` : `Renamed to ${p.name}.`, "success");
          // Reload first so the new property is in the list before selecting it.
          void propsQ.reload().then(() => {
            if (created) setPropertyId(p.id);
          });
        }}
      />

      {!propsQ.data ? (
        <LoadState
          loading={propsQ.loading}
          error={propsQ.error}
          onRetry={() => void propsQ.reload()}
          errorTitle="We couldn't load your properties."
        />
      ) : properties.length === 0 ? (
        <div className="studio-empty-list space-y-3">
          <p>No properties yet. Add your first hotel or venue, then add its rooms and halls.</p>
          <button
            type="button"
            className="studio-btn-secondary admin-btn-primary"
            onClick={() => setPropertyDialog({ open: true, property: null })}
          >
            <IconPlus />
            Add property
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-2">
            <label className="block min-w-[12rem] flex-1 sm:max-w-sm">
              <span className="admin-label">Property</span>
              <select className="studio-field" value={propertyId ?? ""} onChange={(e) => setPropertyId(e.target.value)}>
                {properties.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.space_count} {p.space_count === 1 ? "space" : "spaces"})
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="studio-btn-secondary"
              onClick={() => setPropertyDialog({ open: true, property: null })}
            >
              <IconPlus />
              Add property
            </button>
            <button
              type="button"
              className="studio-btn-secondary"
              disabled={!property}
              onClick={() => property && setPropertyDialog({ open: true, property })}
            >
              <IconEdit />
              Rename
            </button>
            <button
              type="button"
              className="studio-btn-secondary studio-btn-danger"
              disabled={!property || property.space_count > 0}
              title={property && property.space_count > 0 ? "Delete its spaces first." : undefined}
              onClick={() => property && setPending({ kind: "delete-property", property })}
            >
              <IconTrashAdmin />
              Delete property
            </button>
          </div>

          <section className="admin-card min-w-0 p-4" aria-labelledby="inv-spaces">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 id="inv-spaces" className="admin-section-title">
                  Spaces{property ? ` at ${property.name}` : ""}
                </h3>
                {property?.timezone ? <p className="admin-faint text-xs">Time zone: {property.timezone}</p> : null}
              </div>
              <button
                type="button"
                className="studio-btn-secondary admin-btn-primary"
                disabled={!propertyId}
                onClick={() => setSpaceDialog({ open: true, space: null })}
              >
                <IconPlus />
                Add space
              </button>
            </div>
            <AdminTable
              caption="Spaces"
              columns={columns}
              rows={spacesQ.data}
              rowKey={(s) => s.id}
              loading={spacesQ.loading}
              error={spacesQ.error}
              onRetry={() => void spacesQ.reload()}
              errorTitle="We couldn't load the spaces."
              empty="No spaces at this property yet. Add a ballroom, boardroom or room block so the agent can offer it."
            />
          </section>
        </div>
      )}
    </AdminPanel>
  );
}
