import type { RefObject } from "react";
import type { PickHighlightBox } from "../../lib/designerPreviewElementPicker";

type Props = {
  hoverBox: PickHighlightBox | null;
  lockedBox: PickHighlightBox | null;
  pickMode: boolean;
  contentHeight: number;
  shieldRef: RefObject<HTMLDivElement | null>;
};

function Ring({ box, variant }: { box: PickHighlightBox; variant: "hover" | "locked" }) {
  return (
    <div
      className={`studio-preview-pick-ring studio-preview-pick-ring--${variant}`}
      style={{
        top: box.top,
        left: box.left,
        width: box.width,
        height: box.height,
      }}
      aria-hidden
    >
      <svg className="studio-preview-pick-ring-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
        <rect x="1.5" y="1.5" width="97" height="97" rx="4" ry="4" fill="none" />
      </svg>
    </div>
  );
}

export default function PreviewTargetHighlight({
  hoverBox,
  lockedBox,
  pickMode,
  contentHeight,
  shieldRef,
}: Props) {
  const showLayer = pickMode || Boolean(lockedBox);
  if (!showLayer) return null;

  const showHover = pickMode && hoverBox;
  const showLocked = Boolean(lockedBox);

  return (
    <div
      className="studio-preview-pick-layer"
      style={{ height: Math.max(contentHeight, 320) }}
      aria-hidden={!pickMode}
    >
      {pickMode ? (
        <>
          <div
            ref={shieldRef as RefObject<HTMLDivElement>}
            className="studio-preview-pick-shield"
            title="Click to select a section"
          />
          {!showHover ? (
            <p className="studio-preview-pick-hint">Click a section or card in the preview</p>
          ) : null}
        </>
      ) : null}
      {showLocked && lockedBox ? <Ring box={lockedBox} variant="locked" /> : null}
      {showHover && hoverBox ? <Ring box={hoverBox} variant="hover" /> : null}
    </div>
  );
}
