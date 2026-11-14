import { AnimatePresence, motion, useDragControls, useReducedMotion } from "motion/react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

const stack: string[] = [];

/** id of the element every sheet covers: the app frame */
export const FRAME_ID = "kori-frame";

/** Only the top sheet takes focus and clicks: the screen and any sheet under it go inert. */
function syncInert() {
  const frame = document.getElementById(FRAME_ID);
  if (!frame) return;
  const top = stack[stack.length - 1];
  for (const el of Array.from(frame.children) as HTMLElement[]) {
    const sheet = el.dataset.sheet;
    el.inert = sheet ? sheet !== top : stack.length > 0;
  }
}

interface Props {
  open: boolean;
  onClose: () => void;
  label: string;
  children: ReactNode;
  /** full: nearly the whole app height (coach, lesson). auto: as tall as its content, up to 90%. */
  size?: "full" | "auto";
  z?: number;
  /** element to focus when the sheet opens; defaults to the panel itself */
  initialFocus?: React.RefObject<HTMLElement | null>;
}

/** A sheet that lives inside the app frame (absolute, not fixed), so it works in the phone frame on a laptop too. */
export function Sheet({ open, onClose, label, children, size = "auto", z = 40, initialFocus }: Props) {
  const reduce = useReducedMotion();
  const id = useId();
  const panel = useRef<HTMLDivElement>(null);
  const drag = useDragControls();
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    stack.push(id);
    syncInert();
    const f = requestAnimationFrame(() => (initialFocus?.current ?? panel.current)?.focus({ preventScroll: true }));
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && stack[stack.length - 1] === id) {
        e.stopPropagation();
        closeRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(f);
      window.removeEventListener("keydown", onKey);
      const i = stack.indexOf(id);
      if (i >= 0) stack.splice(i, 1);
      syncInert();
      if (prev && document.contains(prev)) prev.focus({ preventScroll: true });
    };
  }, [open, id, initialFocus]);

  const tree = (
    <AnimatePresence>
      {open && (
        <div data-sheet={id} className="absolute inset-0 flex flex-col justify-end" style={{ zIndex: z }}>
          <motion.div
            className="absolute inset-0 bg-ink/35"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-label={label}
            tabIndex={-1}
            className={
              "relative flex min-h-0 flex-col rounded-t-[22px] bg-ground shadow-sheet outline-none " +
              (size === "full" ? "h-[calc(100%-10px)] sm:h-[calc(100%-14px)]" : "max-h-[90%]")
            }
            initial={reduce ? { opacity: 0 } : { y: "100%" }}
            animate={reduce ? { opacity: 1 } : { y: 0 }}
            exit={reduce ? { opacity: 0 } : { y: "100%" }}
            transition={reduce ? { duration: 0.15 } : { type: "spring", stiffness: 420, damping: 42, mass: 0.9 }}
            drag={reduce ? false : "y"}
            dragControls={drag}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.6 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 110 || info.velocity.y > 600) onClose();
            }}
          >
            <div
              className="flex h-6 shrink-0 cursor-grab touch-none items-center justify-center active:cursor-grabbing"
              onPointerDown={(e) => drag.start(e)}
              aria-hidden
            >
              <div className="h-1 w-9 rounded-full bg-line-strong" />
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
  // sheets opened from inside a scrolling screen still cover the whole app frame
  const frame = typeof document !== "undefined" ? document.getElementById(FRAME_ID) : null;
  return frame ? createPortal(tree, frame) : tree;
}
