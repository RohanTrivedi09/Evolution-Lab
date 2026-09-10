export type Dataset = {
  days: string[];
  periods: string[];
  rooms: { id: string; capacity?: number; type?: string }[];
  courses: {
    id: string; name: string; faculty_id: string; group_ids: string[];
    preferred_periods?: { day: string; period: string }[];
  }[];
};

export type Detail = {
  session_id: string;
  category: string;
  message: string;
  severity?: 'hard' | 'soft';
  cost?: number;
};

export type Score = {
  total_cost: number;
  normalized_fitness?: number;
  hard_violations: number;
  soft_violations: number;
  group_gaps: number;
  daily_fragmentation?: number;
  violation_details?: Detail[];
  hard_breakdown?: Record<string, number>;
  soft_breakdown?: Record<string, number>;
  objectives?: Record<string, number>;
  cost_by_course?: Record<string, number>;
  cost_by_group?: Record<string, number>;
  cost_by_faculty?: Record<string, number>;
  fuzzy?: FuzzyReport | null;
};

export type FuzzyReport = {
  discomfort: number;
  inputs: Record<string, number>;
  memberships: Record<string, Record<string, number>>;
  firings: { rule: string; consequent: string; strength: number }[];
};

export type Slot = { day: string; period: string; room_id: string };
export type Schedule = Record<string, Slot>;

export type Point = {
  iteration: number;
  evaluations: number;
  best_cost: number;
  best_fitness: number;
  hard_violations: number;
  schedule?: Schedule;
  average_cost?: number;
  event?: string;
  /** simulated annealing */
  temperature?: number;
  acceptance_probability?: number;
  accepted_worse_moves?: number;
  escaped_local_optima?: number;
  /** hill climbing */
  neighbor_cost?: number;
  current_cost?: number;
  accepted_moves?: number;
  rejected_moves?: number;
  plateaus?: number;
  restarts?: number;
  local_optimum_detected?: boolean;
  /** genetic algorithm */
  population_size?: number;
  population_diversity?: number;
  mutation_rate?: number;
  crossover_rate?: number;
  elite_count?: number;
  /** particle swarm */
  particle_count?: number;
  swarm_diversity?: number;
  average_velocity?: number;
  convergence_percentage?: number;
};

export type Result = {
  schedule: Schedule;
  score: Score;
  history: Point[];
  runtime_ms: number;
  evaluations: number;
  trajectory?: { evaluations: number; cost: number; placement: (string | number)[][] }[];
};

export type Run = {
  run_id: string;
  status: string;
  algorithm: string;
  max_evaluations?: number;
  progress?: number;
  error?: string;
  result?: Result;
  latest?: Point;
};

export type Comparison = {
  comparison_id: string;
  status: string;
  runs?: Run[];
  max_evaluations?: number;
};

export type ExperimentRow = {
  algorithm: string;
  runs: number;
  mean_cost: number;
  std_cost: number;
  best_cost: number;
  worst_cost: number;
  median_cost: number;
  feasible_rate: number;
  mean_evaluations_to_feasible: number | null;
  mean_runtime_ms: number;
  seed_wins: number;
};

export type Experiment = {
  experiment_id: string;
  status: string;
  progress?: number;
  error?: string;
  dataset_id?: string;
  seeds?: number[];
  max_evaluations?: number;
  total_trials?: number;
  summary?: ExperimentRow[];
  trials?: { algorithm: string; seed: number; total_cost: number; hard_violations: number }[];
};

export const ALGORITHMS = [
  'hill_climbing', 'simulated_annealing', 'genetic_algorithm', 'particle_swarm',
] as const;

export type AlgorithmName = (typeof ALGORITHMS)[number];

/** "hill_climbing" -> "hill climbing" */
export const label = (value: string) => value.split('_').join(' ');
