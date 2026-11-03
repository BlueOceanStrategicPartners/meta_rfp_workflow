import { IconTargetPick } from "./TemplateIconButton";
import type { ChatPreviewTargetAttachment } from "../../lib/designerApi";

type Props = {
  target: ChatPreviewTargetAttachment;
};

export default function PreviewTargetActionCard({ target }: Props) {
  const title =
    target.sectionLabel ||
    target.textSnippet.slice(0, 64) ||
    "Selected section";

  return (
    <div className="studio-preview-target-action-card">
      <div className="studio-preview-target-action-card-icon" aria-hidden>
        <IconTargetPick />
      </div>
      <div className="min-w-0 flex-1">
        <p className="studio-preview-target-action-card-kicker">Preview target</p>
        <p className="studio-preview-target-action-card-title">{title}</p>
      </div>
    </div>
  );
}
