import { forwardRef, useImperativeHandle, useRef, type TextareaHTMLAttributes } from "react";
import { useCustomScrollChrome } from "../../hooks/useCustomScrollChrome";

const COMPOSER_MAX_LINES = 10;

export function resizeComposerField(el: HTMLTextAreaElement) {
  el.style.height = "0px";
  const styles = getComputedStyle(el);
  const lineHeight = Number.parseFloat(styles.lineHeight) || 20;
  const padding = Number.parseFloat(styles.paddingTop) + Number.parseFloat(styles.paddingBottom);
  const maxHeight = lineHeight * COMPOSER_MAX_LINES + padding;
  const next = Math.min(el.scrollHeight, maxHeight);
  el.style.height = `${next}px`;
  el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
}

export function resetComposerField(el: HTMLTextAreaElement) {
  el.value = "";
  el.style.height = "";
  el.style.overflowY = "hidden";
}

type Props = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "rows"> & {
  onValueChange?: (value: string) => void;
};

/** Multiline composer field with deck-style custom scrollbar (max 10 lines). */
const ComposerMultilineField = forwardRef<HTMLTextAreaElement, Props>(function ComposerMultilineField(
  { className = "", onChange, onValueChange, ...props },
  ref,
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => textareaRef.current as HTMLTextAreaElement);

  const { canScroll, thumbHeight, thumbTop, scrollToPointer, remeasure } = useCustomScrollChrome(textareaRef);

  return (
    <div className="client-custom-scroll client-composer-scroll min-w-0 flex-1 self-center">
      <textarea
        ref={textareaRef}
        rows={1}
        {...props}
        className={[
          "client-custom-scroll__viewport client-composer-input w-full resize-none bg-transparent px-1 py-2 text-sm leading-5 outline-none ring-0",
          canScroll ? "client-composer-input--scrollable" : "",
          className,
        ].join(" ")}
        onChange={(e) => {
          onValueChange?.(e.target.value);
          resizeComposerField(e.target);
          requestAnimationFrame(() => remeasure());
          onChange?.(e);
        }}
      />
      {canScroll ? (
        <div
          className="client-custom-scroll__track client-composer-scroll__track"
          role="presentation"
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            scrollToPointer(e.clientY, e.currentTarget);
          }}
          onPointerMove={(e) => {
            if (e.buttons !== 1) return;
            scrollToPointer(e.clientY, e.currentTarget);
          }}
        >
          <div
            className="client-custom-scroll__thumb"
            style={{ height: thumbHeight, top: thumbTop }}
          />
        </div>
      ) : null}
    </div>
  );
});

export default ComposerMultilineField;
