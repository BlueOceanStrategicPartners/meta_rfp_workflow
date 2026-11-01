import { useMemo } from "react";
import { compileLocalTemplatePreview } from "../../lib/designerTemplatePreview";
import type { ProposalTemplate } from "../../lib/designerApi";

type Props = {
  template: ProposalTemplate;
  selected: boolean;
  onSelect: () => void;
};

export default function TemplateLibraryCard({ template, selected, onSelect }: Props) {
  const previewDoc = useMemo(
    () =>
      compileLocalTemplatePreview(
        template.html_markup,
        template.css_stylesheet,
        template.js_script || ""
      ),
    [template.html_markup, template.css_stylesheet, template.js_script]
  );

  const hasContent = Boolean((template.html_markup || "").trim());

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`studio-template-card w-full text-left transition ${selected ? "studio-template-card--active" : ""}`}
    >
      <div className="studio-template-card-preview" aria-hidden>
        {hasContent ? (
          <iframe
            title=""
            tabIndex={-1}
            className="studio-template-card-iframe"
            sandbox="allow-scripts allow-same-origin"
            loading="lazy"
            srcDoc={previewDoc}
          />
        ) : (
          <div className="studio-template-card-empty">
            <span className="text-2xl opacity-40">◇</span>
            <span className="text-[10px] text-white/35">No layout yet</span>
          </div>
        )}
      </div>
      <div className="studio-template-card-meta">
        <p className="truncate text-sm font-medium text-white/95">{template.name}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-white/40">
          <time dateTime={template.updated_at}>{new Date(template.updated_at).toLocaleString()}</time>
          {template.is_default && (
            <span className="rounded-full bg-amber-500/20 px-1.5 py-0.5 font-medium text-amber-200">
              Default
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
