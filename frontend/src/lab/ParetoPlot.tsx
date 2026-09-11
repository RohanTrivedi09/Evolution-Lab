import React, { useMemo, useState } from 'react';
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip,
         XAxis, YAxis, ZAxis } from 'recharts';

import { TimetableGrid } from '../components/TimetableGrid';
import { OBJECTIVE_LABELS } from '../types';
import type { Dataset, ParetoSolution } from '../types';

const AXES = Object.keys(OBJECTIVE_LABELS);

/**
 * The Pareto front: timetables that no other timetable beats on every objective.
 *
 * A weighted sum decides the trade-off before the search starts. This hands it back -
 * each point is a schedule that is better than the others at something, and picking one
 * is a judgement about priorities rather than a calculation.
 */
export function ParetoPlot({ front, dataset }: { front: ParetoSolution[]; dataset: Dataset | null }) {
  const [xKey, setXKey] = useState('group_gaps');
  const [yKey, setYKey] = useState('soft_penalty');
  const [selected, setSelected] = useState(0);

  const points = useMemo(() => front.map((solution, index) => ({
    index,
    x: solution.objectives[xKey] ?? 0,
    y: solution.objectives[yKey] ?? 0,
    cost: solution.total_cost,
  })), [front, xKey, yKey]);

  const chosen = front[Math.min(selected, front.length - 1)];
  if (!chosen) return null;

  return (
    <section className="panel pareto">
      <div className="panel-title">
        <div>
          <p className="eyebrow">PARETO FRONT · MULTI-OBJECTIVE</p>
          <h2>{front.length} timetables, none better than the rest</h2>
        </div>
        <span>{front.length} non-dominated</span>
      </div>
      <p className="note">
        Every point is a schedule that beats the others at something and loses at something
        else. There is no single winner here — choosing one is a decision about priorities.
        Click a point to load its timetable.
      </p>

      <div className="pareto-axes">
        <label>Horizontal
          <select value={xKey} onChange={e => setXKey(e.target.value)}>
            {AXES.map(key => <option key={key} value={key}>{OBJECTIVE_LABELS[key]}</option>)}
          </select>
        </label>
        <label>Vertical
          <select value={yKey} onChange={e => setYKey(e.target.value)}>
            {AXES.map(key => <option key={key} value={key}>{OBJECTIVE_LABELS[key]}</option>)}
          </select>
        </label>
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 12, right: 16, bottom: 24, left: 8 }}>
          <CartesianGrid strokeOpacity={0.15} />
          <XAxis type="number" dataKey="x" name={OBJECTIVE_LABELS[xKey]} tick={{ fontSize: 11 }}
                 label={{ value: OBJECTIVE_LABELS[xKey], position: 'insideBottom', offset: -12, fontSize: 11 }} />
          <YAxis type="number" dataKey="y" name={OBJECTIVE_LABELS[yKey]} tick={{ fontSize: 11 }} width={56} />
          <ZAxis range={[110, 110]} />
          <Tooltip cursor={{ strokeOpacity: 0.2 }}
                   formatter={(value: number, name: string) => [value, name]} />
          <Scatter data={points} fill="var(--swarm)" isAnimationActive={false}
                   onClick={(point: any) => setSelected(point.index)} cursor="pointer" />
        </ScatterChart>
      </ResponsiveContainer>

      <div className="pareto-picker">
        {front.map((solution, index) => (
          <button key={index} type="button"
                  className={`secondary ${index === selected ? 'chosen' : ''}`}
                  onClick={() => setSelected(index)}>
            #{index + 1} · {solution.hard_violations} hard
          </button>
        ))}
      </div>

      <div className="telemetry-grid">
        {AXES.map(key => (
          <div key={key}>
            <span>{OBJECTIVE_LABELS[key]}</span>
            <b className={key === 'hard_violations' && chosen.objectives[key] > 0 ? 'bad' : ''}>
              {Number(chosen.objectives[key] ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </b>
          </div>
        ))}
      </div>

      <TimetableGrid dataset={dataset} schedule={chosen.schedule} scope={`pareto-${selected}`} />
    </section>
  );
}
