import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { TimetableGrid } from '../components/TimetableGrid';
import { getDataset, raceAll } from '../api/client';
import { COMPARISON_ALGORITHMS, label } from '../types';
import type { Comparison, ComparisonAlgorithm, Dataset, Point, Run } from '../types';
import { Scene } from './Scene';

const DATASET_ID = 'small-college';
const BUDGET = 1200;
const SEED = 42;
const CACHE_KEY = `evolution-lab-story-v3:${DATASET_ID}:${BUDGET}:${SEED}`;

/** Stretch the cooling schedule over the whole budget: the default 0.95 is tuned for a
 *  ~100-iteration run and would flatten to zero in the first tenth of the scroll. */
const STORY_PARAMS = { initial_temperature: 1000, cooling_rate: 0.994 };

const TINT: Record<string, string> = {
  hill_climbing: '#d86f4d',
  simulated_annealing: '#9a5741',
  genetic_algorithm: '#597d73',
  particle_swarm: '#7a6ea8',
};

type Readout = [string, React.ReactNode][];

const NARRATIVE: Record<ComparisonAlgorithm, {
  title: string;
  paragraphs: React.ReactNode[];
  readout: (point: Point) => Readout;
}> = {
  hill_climbing: {
    title: 'Hill Climbing takes the first step downhill',
    paragraphs: [
      'It keeps only changes that make the timetable no worse. That is enough to fix the obvious clashes very fast — most of the improvement happens in the first few hundred evaluations.',
      'Then it stalls. Every single move it can see makes things worse, so it stops moving even though better timetables exist elsewhere. That is a local optimum, and the counter below shows when it gives up and restarts somewhere new.',
    ],
    readout: point => [
      ['Accepted', point.accepted_moves ?? '—'],
      ['Rejected', point.rejected_moves ?? '—'],
      ['Plateaus', point.plateaus ?? '—'],
      ['Restarts', point.restarts ?? 0],
    ],
  },
  simulated_annealing: {
    title: 'Simulated Annealing accepts bad moves on purpose',
    paragraphs: [
      'Early on the temperature is high, so a worse timetable still has a good chance of being accepted. That is what lets it walk out of the trap Hill Climbing fell into.',
      'As the temperature cools the same worse move becomes far less likely to survive. The search hardens from wandering into refining — watch the acceptance probability collapse as you scroll.',
    ],
    readout: point => [
      ['Temperature', point.temperature?.toFixed(1) ?? '—'],
      ['Accept chance', point.acceptance_probability ?? '—'],
      ['Worse accepted', point.accepted_worse_moves ?? 0],
      ['Escapes', point.escaped_local_optima ?? 0],
    ],
  },
  genetic_algorithm: {
    title: 'The Genetic Algorithm breeds a population',
    paragraphs: [
      'Instead of one timetable it keeps thirty. Each generation, tournament selection picks parents, crossover mixes their session placements into a child, and mutation nudges a few genes.',
      'Diversity is the number of genuinely different timetables still alive. It falls steadily as good genes take over — useful, until it falls so far that the population stops exploring at all.',
    ],
    readout: point => [
      ['Generation', point.iteration],
      ['Population', point.population_size ?? '—'],
      ['Diversity', point.population_diversity ?? '—'],
      ['Crossover', point.crossover_rate ?? '—'],
    ],
  },
  particle_swarm: {
    title: 'Particle Swarm shares what it finds',
    paragraphs: [
      'Timetables are not continuous, so velocity here is a set of per-gene adoption probabilities: each particle copies placements from its own best and from the swarm best, then explores a little on its own.',
      'Information sharing makes it converge quickly. The risk is the mirror image of the GA — pull the particles too hard toward one answer and the swarm collapses before it has looked around.',
    ],
    readout: point => [
      ['Particles', point.particle_count ?? '—'],
      ['Diversity', point.swarm_diversity ?? '—'],
      ['Velocity', point.average_velocity ?? '—'],
      ['Converged', `${point.convergence_percentage ?? 0}%`],
    ],
  },
};

/** Best-so-far cost for every algorithm sampled on one shared evaluation axis. */
function anytimeCurves(runs: Run[], samples = 60) {
  const finished = runs.filter(run => run.result);
  if (!finished.length) return [];
  const ceiling = Math.max(...finished.map(run => run.result!.evaluations));
  return Array.from({ length: samples }, (_, index) => {
    const evaluations = Math.round(((index + 1) * ceiling) / samples);
    const row: Record<string, number> = { evaluations };
    for (const run of finished) {
      let best: number | undefined;
      for (const point of run.result!.history) {
        if (point.evaluations > evaluations) break;
        best = point.best_cost;
      }
      if (best !== undefined) row[run.algorithm] = best;
    }
    return row;
  });
}

function Cost({ point }: { point?: Point }) {
  if (!point) return null;
  return (
    <div className="scene-metrics">
      <div><span>Cost</span><b>{point.best_cost.toLocaleString()}</b></div>
      <div><span>Hard clashes</span><b className={point.hard_violations ? 'bad' : 'good'}>{point.hard_violations}</b></div>
      <div><span>Evaluations</span><b>{point.evaluations.toLocaleString()}</b></div>
    </div>
  );
}

function AlgorithmScene({ run, dataset }: { run: Run; dataset: Dataset | null }) {
  const history = run.result?.history ?? [];
  const copy = NARRATIVE[run.algorithm as ComparisonAlgorithm];
  if (!history.length || !copy) return null;

  return (
    <Scene
      eyebrow={`Strategy · ${label(run.algorithm)}`}
      title={copy.title}
      paragraphs={copy.paragraphs}
      steps={history.length}
      length={340}
      visual={step => {
        const point = history[Math.min(step, history.length - 1)];
        return (
          <div className="scene-stage" style={{ ['--tint' as string]: TINT[run.algorithm] }}>
            <Cost point={point} />
            <TimetableGrid dataset={dataset} scope={run.algorithm}
                           schedule={point.schedule ?? run.result!.schedule} />
            <div className="scene-readout">
              {copy.readout(point).map(([name, value]) => (
                <div key={name}><span>{name}</span><b>{value}</b></div>
              ))}
            </div>
            <p className="scene-event">{point.event}</p>
          </div>
        );
      }}
    />
  );
}

export function Story({ onEnterLab }: { onEnterLab: () => void }) {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getDataset(DATASET_ID).then(setDataset).catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (cached) {
      try {
        setComparison(JSON.parse(cached));
        return;
      } catch {
        sessionStorage.removeItem(CACHE_KEY);
      }
    }
    raceAll(DATASET_ID, BUDGET, SEED, STORY_PARAMS)
      .then(result => {
        setComparison(result);
        try {
          sessionStorage.setItem(CACHE_KEY, JSON.stringify(result));
        } catch {
          /* story still works without the cache; a re-scroll just refetches */
        }
      })
      .catch(e => setError(e.message));
  }, []);

  const runs = useMemo(() => {
    const byName = new Map((comparison?.runs ?? []).map(run => [run.algorithm, run]));
    return COMPARISON_ALGORITHMS.map(name => byName.get(name)).filter((run): run is Run => !!run?.result);
  }, [comparison]);

  useEffect(() => {
    if (runs.length) window.scrollTo({ top: 0 });
  }, [runs.length]);

  const curves = useMemo(() => anytimeCurves(runs), [runs]);
  const first = runs[0]?.result;

  const scale = useMemo(() => {
    if (!dataset || !first) return null;
    const sessions = Object.keys(first.schedule).length;
    const slots = dataset.days.length * dataset.periods.length * dataset.rooms.length;
    return { sessions, slots, exponent: sessions * Math.log10(slots) };
  }, [dataset, first]);

  if (error) return <main className="story"><p className="error" role="alert">{error}</p></main>;

  if (!comparison || !runs.length || !scale) {
    return (
      <main className="story">
        <div className="story-loading">
          <div className="spinner" aria-hidden="true" />
          <h2>Running all four strategies…</h2>
          <p>{BUDGET.toLocaleString()} fitness evaluations each, on the same dataset and seed.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="story">
      <header className="story-hero">
        <p className="eyebrow">Soft computing · scrollytelling</p>
        <h1>How four algorithms<br /><i>search</i> for a timetable</h1>
        <p className="lede">
          Every strategy below solves the same problem, scored by the same evaluator, on the
          same budget of {BUDGET.toLocaleString()} fitness evaluations. Scroll to drive each
          search forward yourself.
        </p>
        <span className="scroll-cue" aria-hidden="true">Scroll ↓</span>
      </header>

      <Scene
        eyebrow="The problem"
        title="You cannot simply try them all"
        paragraphs={[
          <>There are {scale.sessions} sessions to place, and each one could go in any of {scale.slots} day-period-room combinations.</>,
          'That makes the number of possible timetables larger than the number of atoms in a swimming pool. Checking them one by one is not slow — it is impossible. So we search instead of enumerate.',
        ]}
        steps={40}
        length={260}
        visual={(_, progress) => {
          const shown = scale.exponent * progress;
          const mantissa = Math.pow(10, shown % 1);
          return (
            <div className="scene-stage counter-stage">
              <div className="counter">
                <span>{mantissa.toFixed(2)}</span>
                <em>× 10<sup>{Math.floor(shown)}</sup></em>
              </div>
              <p className="counter-caption">possible timetables</p>
              <div className="counter-facts">
                <div><span>Sessions</span><b>{scale.sessions}</b></div>
                <div><span>Slots each</span><b>{scale.slots}</b></div>
                <div><span>Budget</span><b>{BUDGET.toLocaleString()}</b></div>
              </div>
            </div>
          );
        }}
      />

      {runs.map(run => <AlgorithmScene key={run.run_id} run={run} dataset={dataset} />)}

      <Scene
        eyebrow="Head to head"
        title="Same problem, same budget, four answers"
        paragraphs={[
          'Cost is plotted against fitness evaluations rather than iterations. One hill-climbing iteration costs a single evaluation; one genetic generation costs a whole population — so an iteration axis would compare budgets, not strategies.',
          'Lower is better, and every line stops at the same place on the x-axis. That is what makes this a fair race.',
        ]}
        steps={curves.length || 1}
        length={300}
        visual={(_, progress) => (
          <div className="scene-stage">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={curves.slice(0, Math.max(2, Math.ceil(curves.length * progress)))}>
                <XAxis dataKey="evaluations" tick={{ fontSize: 11 }} type="number"
                       domain={[0, curves[curves.length - 1]?.evaluations ?? BUDGET]} />
                <YAxis tick={{ fontSize: 11 }} width={64} />
                <Tooltip />
                {runs.map(run => (
                  <Line key={run.algorithm} type="stepAfter" dataKey={run.algorithm}
                        stroke={TINT[run.algorithm]} strokeWidth={2} dot={false}
                        isAnimationActive={false} name={label(run.algorithm)} />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <div className="scene-legend">
              {[...runs]
                .sort((a, b) => a.result!.score.total_cost - b.result!.score.total_cost)
                .map(run => (
                  <div key={run.algorithm}>
                    <i style={{ background: TINT[run.algorithm] }} />
                    <span>{label(run.algorithm)}</span>
                    <b>{run.result!.score.total_cost.toLocaleString()}</b>
                    <small>{run.result!.score.hard_violations} hard</small>
                  </div>
                ))}
            </div>
          </div>
        )}
      />

      <section className="story-finale">
        <p className="eyebrow">Your turn</p>
        <h2>Soft computing does not hand you one answer.</h2>
        <p>
          It gives you a way to explore good answers under competing goals — and a way to
          say honestly which strategy earned its result. Open the lab to change the weights,
          race the strategies yourself, or edit a timetable and hand your edit back to an
          algorithm to repair.
        </p>
        <motion.button whileHover={{ y: -2 }} whileTap={{ y: 0 }} onClick={onEnterLab}>
          Open the lab →
        </motion.button>
      </section>
    </main>
  );
}
