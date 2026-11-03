import { useEffect, useMemo, useState, type KeyboardEvent, type MouseEvent } from "react";
import { compileLocalTemplatePreview } from "../../lib/designerTemplatePreview";
import type { ProposalTemplate, TemplateRevision } from "../../lib/designerApi";
import TemplateIconButton, {
  IconDuplicate,
  IconExport,
  IconHistory,
  IconMoreVertical,
  IconSave,
  IconStar,
  IconTrash,
} from "./TemplateIconButton";

export type TemplateLibraryCardActions = {
  onDuplicate: () => void;
  onDelete: () => void;
  onSetDefault: () => void;
  onExport: () => void;
};

type Props = {
  template: ProposalTemplate;
  selected: boolean;
  onSelect: () => void;
  busy?: boolean;
  displayName: string;
  onNameChange?: (name: string) => void;
  menuOpen: boolean;
  onMenuToggle: () => void;
  actionsEnabled: boolean;
  actions: TemplateLibraryCardActions;
  isDefault: boolean;
  revisions: TemplateRevision[];
  onOpenHistory: () => void;
  isDraft?: boolean;
  isDirty?: boolean;
  onSave?: () => void;
};

export default function TemplateLibraryCard({
  template,
  selected,
  onSelect,
  busy,
  displayName,
  onNameChange,
  menuOpen,
  onMenuToggle,
  actionsEnabled,
  actions,
  isDefault,
  revisions,
  onOpenHistory,
  isDraft,
  isDirty,
  onSave,
}: Props) {
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(displayName);

  useEffect(() => {
    if (!renaming) setRenameValue(displayName);
  }, [displayName, renaming]);

  const previewDoc = useMemo(
    () =>
      compileLocalTemplatePreview(
        template.html_markup,
        template.css_stylesheet,
        template.js_script || "",
        { thumbnail: true },
      ),
    [template.html_markup, template.css_stylesheet, template.js_script],
  );

  const hasContent = Boolean((template.html_markup || "").trim());
  const showActionsRow = menuOpen && actionsEnabled;
  const showSave = Boolean(selected && isDirty && onSave);

  const handleMenuClick = () => {
    if (!selected) onSelect();
    onMenuToggle();
  };

  const handleHistoryClick = () => {
    if (!selected) onSelect();
    onOpenHistory();
  };

  const startRename = (e: MouseEvent) => {
    e.stopPropagation();
    if (!selected || !onNameChange) return;
    setRenameValue(displayName);
    setRenaming(true);
  };

  const commitRename = () => {
    setRenaming(false);
    if (onNameChange && renameValue.trim()) {
      onNameChange(renameValue.trim());
    }
  };

  const onRenameKey = (e: KeyboardEvent) => {
    if (e.key === "Enter") commitRename();
    if (e.key === "Escape") {
      setRenaming(false);
      setRenameValue(displayName);
    }
  };

  return (
    <div
      className={`studio-template-card w-full transition ${selected ? "studio-template-card--active" : ""} ${isDraft ? "border-dashed border-violet-400/35" : ""}`}
    >
      <button type="button" onClick={onSelect} className="block w-full text-left">
        <div className="studio-template-card-preview" aria-hidden>
          {hasContent ? (
            <div className="studio-template-card-preview-inset">
              <iframe
                title=""
                tabIndex={-1}
                className="studio-template-card-iframe"
                sandbox="allow-scripts allow-same-origin"
                loading="lazy"
                srcDoc={previewDoc}
              />
            </div>
          ) : (
            <div className="studio-template-card-empty m-2 rounded-lg">
              <span className="text-2xl opacity-40">◇</span>
              <span className="studio-template-card-empty-hint text-[10px]">No layout yet</span>
            </div>
          )}
        </div>
      </button>

      <div className="studio-template-card-meta studio-template-card-footer">
        <div className="flex min-w-0 items-start gap-1.5">
          <div className="min-w-0 flex-1" onClick={(e) => e.stopPropagation()}>
            {renaming && selected && onNameChange ? (
              <input
                className="studio-field !py-1 !text-xs"
                value={renameValue}
                autoFocus
                onChange={(e) => setRenameValue(e.target.value)}
                onBlur={commitRename}
                onKeyDown={onRenameKey}
                aria-label="Rename template"
              />
            ) : (
              <p
                className={`studio-template-card-title truncate text-sm font-medium ${selected && onNameChange ? "cursor-text" : ""}`}
                onDoubleClick={startRename}
                title={selected && onNameChange ? "Double-click to rename" : undefined}
              >
                {displayName}
              </p>
            )}
            <div className="studio-template-card-submeta mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px]">
              {!isDraft && (
                <time dateTime={template.updated_at}>{new Date(template.updated_at).toLocaleString()}</time>
              )}
              {isDraft && <span className="studio-template-draft-label">Unsaved draft</span>}
              {isDefault && <span className="studio-template-default-badge">Default</span>}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
            {!isDraft && (
              <TemplateIconButton
                micro
                label={revisions.length ? "Version history" : "No version history yet"}
                disabled={busy || revisions.length === 0}
                onClick={handleHistoryClick}
              >
                <IconHistory />
              </TemplateIconButton>
            )}
            <TemplateIconButton
              micro
              label={menuOpen ? "Hide actions" : "Template actions"}
              selected={menuOpen}
              disabled={busy}
              onClick={handleMenuClick}
            >
              <IconMoreVertical />
            </TemplateIconButton>
          </div>
        </div>

        {showSave ? (
          <div className="mt-2 flex w-full justify-center" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              disabled={busy}
              onClick={() => onSave?.()}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-emerald-400/45 bg-gradient-to-r from-emerald-600/90 to-teal-600/85 px-3 py-1.5 text-[11px] font-semibold text-white shadow-[0_4px_14px_-6px_rgba(16,185,129,0.65)] transition hover:brightness-110 disabled:opacity-50"
            >
              <IconSave />
              Save changes
            </button>
          </div>
        ) : null}

        {showActionsRow ? (
          <div className="studio-template-card-actions-row mt-2 flex flex-wrap items-center justify-center gap-1 border-t pt-2">
            {!isDraft && (
              <TemplateIconButton micro label="Duplicate" disabled={busy} onClick={actions.onDuplicate}>
                <IconDuplicate />
              </TemplateIconButton>
            )}
            {!isDraft && (
              <TemplateIconButton micro label="Delete" variant="danger" disabled={busy} onClick={actions.onDelete}>
                <IconTrash />
              </TemplateIconButton>
            )}
            {!isDraft && (
              <TemplateIconButton
                micro
                label={isDefault ? "Default template" : "Set as default"}
                variant="accent"
                selected={isDefault}
                disabled={busy || isDefault}
                onClick={actions.onSetDefault}
              >
                <IconStar filled={isDefault} />
              </TemplateIconButton>
            )}
            <TemplateIconButton micro label="Export JSON" disabled={busy} onClick={actions.onExport}>
              <IconExport />
            </TemplateIconButton>
          </div>
        ) : null}
      </div>
    </div>
  );
}
