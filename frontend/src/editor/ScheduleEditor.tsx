import React, { useEffect, useState } from 'react';
import { evaluateSchedule } from '../api/client';
import type { Dataset, Schedule, Score } from '../types';
import { TimetableGrid } from '../components/TimetableGrid';

/**
 * An editable timetable.
 *
 * Moving a lecture re-scores it through the same evaluator the optimizers use, so the
 * cost shown here is the cost they would see - the frontend never reimplements the
 * fitness function. Once edited, the draft can be handed back to an algorithm to
 * repair, which is what makes the evaluator tangible rather than abstract.
 */
export function ScheduleEditor({ dataset, datasetId, baseline, baselineCost,
                                 selected, onSelect, onRepair, busy }: {
  dataset: Dataset | null;
  datasetId: string;
  baseline: Schedule;
  baselineCost: number;
  selected: string | null;
  onSelect: (id: string) => void;
  onRepair: (schedule: Schedule) => void;
  busy: boolean;
}) {
  const [draft, setDraft] = useState<Schedule>(baseline);
  const [score, setScore] = useState<Score | null>(null);
  const [error, setError] = useState('');

  // A new run replaces whatever was being edited.
  useEffect(() => { setDraft(baseline); setScore(null); setError(''); }, [baseline]);

  const edited = draft !== baseline;

  useEffect(() => {
    if (!edited) { setScore(null); return; }
    let cancelled = false;
    evaluateSchedule(datasetId, draft)
      .then(result => { if (!cancelled) setScore(result.score); })
      .catch(e => { if (!cancelled) setError((e as Error).message); });
    return () => { cancelled = true; };
  }, [draft, datasetId, edited]);

  const move = (sessionId: string, day: string, period: string) => {
    setDraft(current => {
      const slot = current[sessionId];
      if (!slot || (slot.day === day && slot.period === period)) return current;
      return { ...current, [sessionId]: { ...slot, day, period } };
    });
  };

  const delta = score ? score.total_cost - baselineCost : 0;
  const blame = score?.violation_details?.find(d => d.severity === 'hard');

  return (
    <>
      <p className="editor-hint">
        Drag a lecture to another slot, or focus one and use the arrow keys. Every move is
        re-scored by the same evaluator the algorithms use.
      </p>

      {edited && (
        <div className="editor-bar">
          <span className={`delta ${delta > 0 ? 'worse' : delta < 0 ? 'better' : ''}`}>
            {delta > 0 ? '+' : ''}{delta.toLocaleString()}
          </span>
          <p>
            {error ? error
              : !score ? 'Scoring your edit…'
              : blame ? blame.message
              : delta > 0 ? 'Your edit costs more than the optimised schedule.'
              : delta < 0 ? 'Your edit beats the optimised schedule.'
              : 'Same cost as the optimised schedule.'}
          </p>
          <button type="button" onClick={() => setDraft(baseline)}>Reset</button>
          <button type="button" className="primary" disabled={busy}
                  onClick={() => onRepair(draft)}>
            Repair from here →
          </button>
        </div>
      )}

      <TimetableGrid dataset={dataset} schedule={draft} scope="editor"
                     selected={selected} onSelect={onSelect} onMove={move} />
    </>
  );
}
