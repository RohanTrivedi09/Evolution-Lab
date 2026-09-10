import React, { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

type SceneProps = {
  eyebrow: string;
  title: string;
  paragraphs: React.ReactNode[];
  /** How many discrete states the visual scrubs through as the scene is scrolled. */
  steps: number;
  /** Scroll length in viewport heights. Longer means slower, more deliberate scrubbing. */
  length?: number;
  visual: (step: number, progress: number) => React.ReactNode;
};

/**
 * A scroll-scrubbed scene: a tall section wrapping a sticky viewport-height stage.
 *
 * Scroll position within the section maps to a step index, so the reader drives the
 * optimization forward with the scrollbar instead of watching it replay on a timer.
 *
 * Progress is measured directly from the section's own rect rather than through a
 * scroll-tracking helper: the section is the scroll range, one rect read per frame is
 * cheap, and it stays correct when the page grows underneath it.
 *
 * The rail is written imperatively so a scroll frame does not re-render the stage;
 * only a change of step does.
 *
 * With reduced motion the section collapses to its natural height and renders the
 * final state, because scroll-linked movement is what that preference asks us to avoid.
 */
export function Scene({ eyebrow, title, paragraphs, steps, length = 300, visual }: SceneProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const railRef = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const [step, setStep] = useState(0);
  const lastStep = Math.max(0, steps - 1);

  useEffect(() => {
    if (reduced) return;
    let frame = 0;

    const measure = () => {
      frame = 0;
      const section = sectionRef.current;
      if (!section) return;
      const { top, height } = section.getBoundingClientRect();
      const range = height - window.innerHeight;
      // top === 0 when the section reaches the top of the viewport; -range when its
      // bottom reaches the bottom.
      const progress = range > 0
        ? Math.min(1, Math.max(0, -top / range))
        : (top <= 0 ? 1 : 0);
      if (railRef.current) railRef.current.style.width = `${progress * 100}%`;
      const next = Math.round(progress * lastStep);
      setStep(current => (current === next ? current : next));
    };

    const schedule = () => { if (!frame) frame = requestAnimationFrame(measure); };
    measure();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [reduced, lastStep]);

  const shownStep = reduced ? lastStep : step;
  const shownProgress = lastStep ? shownStep / lastStep : 1;

  return (
    <section
      className={`scene${reduced ? ' scene-static' : ''}`}
      ref={sectionRef}
      style={reduced ? undefined : { height: `${length}vh` }}
    >
      <div className="scene-sticky">
        <div className="scene-copy">
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
          {paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          {!reduced && (
            <div className="scene-rail" aria-hidden="true">
              <span ref={railRef} />
            </div>
          )}
        </div>
        <div className="scene-visual">{visual(shownStep, shownProgress)}</div>
      </div>
    </section>
  );
}
