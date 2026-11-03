import { useEffect, useRef, useState, type RefObject } from "react";
import {
  attachPreviewElementPickerSession,
  measureLockedTargetBox,
  type PickHighlightBox,
  type PreviewElementTarget,
} from "../lib/designerPreviewElementPicker";

type Options = {
  iframeRef: RefObject<HTMLIFrameElement | null>;
  scrollRef: RefObject<HTMLElement | null>;
  shieldRef: RefObject<HTMLElement | null>;
  active: boolean;
  lockedTarget: PreviewElementTarget | null;
  previewDoc: string;
  onSelect: (target: PreviewElementTarget) => void;
};

export function usePreviewElementPicker({
  iframeRef,
  scrollRef,
  shieldRef,
  active,
  lockedTarget,
  previewDoc,
  onSelect,
}: Options): { hoverBox: PickHighlightBox | null; lockedBox: PickHighlightBox | null } {
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const [hoverBox, setHoverBox] = useState<PickHighlightBox | null>(null);
  const [lockedBox, setLockedBox] = useState<PickHighlightBox | null>(null);

  useEffect(() => {
    if (!previewDoc) {
      setHoverBox(null);
      return undefined;
    }

    let detach: (() => void) | undefined;
    let raf = 0;
    let attempts = 0;
    let cancelled = false;

    const syncLocked = () => {
      const box = measureLockedTargetBox(
        iframeRef.current,
        scrollRef.current,
        lockedTarget,
      );
      setLockedBox(box);
    };

    const bind = () => {
      if (cancelled || !active) return false;
      const iframe = iframeRef.current;
      const scrollEl = scrollRef.current;
      const shield = shieldRef.current;
      const doc = iframe?.contentDocument;
      if (!iframe || !scrollEl || !shield || !doc?.body) return false;
      detach?.();
      detach = attachPreviewElementPickerSession({
        iframe,
        scrollEl,
        pointerEl: shield,
        handlers: {
          onHover: (box) => setHoverBox(box),
          onSelect: (target) => onSelectRef.current(target),
        },
      });
      return true;
    };

    const tick = () => {
      if (cancelled) return;
      syncLocked();
      if (active) {
        if (!bind()) {
          attempts += 1;
          if (attempts < 120) {
            raf = window.requestAnimationFrame(tick);
          }
        }
      } else {
        setHoverBox(null);
      }
    };

    raf = window.requestAnimationFrame(tick);
    const iframe = iframeRef.current;
    const onLoad = () => {
      attempts = 0;
      window.requestAnimationFrame(tick);
    };
    iframe?.addEventListener("load", onLoad);

    const scrollEl = scrollRef.current;
    const onScroll = () => {
      syncLocked();
    };
    scrollEl?.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);

    return () => {
      cancelled = true;
      iframe?.removeEventListener("load", onLoad);
      scrollEl?.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
      detach?.();
      detach = undefined;
    };
  }, [active, lockedTarget, previewDoc, iframeRef, scrollRef, shieldRef]);

  useEffect(() => {
    if (!previewDoc || !lockedTarget) {
      return undefined;
    }
    const sync = () => {
      const box = measureLockedTargetBox(
        iframeRef.current,
        scrollRef.current,
        lockedTarget,
      );
      setLockedBox(box);
    };
    sync();
    const t1 = window.setTimeout(sync, 50);
    const t2 = window.setTimeout(sync, 400);
    const scrollEl = scrollRef.current;
    scrollEl?.addEventListener("scroll", sync, { passive: true });
    window.addEventListener("resize", sync);
    const iframe = iframeRef.current;
    iframe?.addEventListener("load", sync);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      scrollEl?.removeEventListener("scroll", sync);
      window.removeEventListener("resize", sync);
      iframe?.removeEventListener("load", sync);
    };
  }, [lockedTarget, previewDoc, iframeRef, scrollRef]);

  return { hoverBox, lockedBox };
}
