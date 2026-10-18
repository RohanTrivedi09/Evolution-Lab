import type { Comparison, Dataset, Experiment, Run, Schedule, Score } from '../types';

/** Set at build time for a deployment; `||` so an empty variable still falls back. */
export const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init);
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `Request failed: ${path}`);
  }
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) => request<T>(path, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
});

export const listDatasets = () =>
  request<{ datasets: any[] }>('/datasets').then(payload => payload.datasets);

export const getDataset = (id: string) => request<Dataset>(`/datasets/${id}`);

export type Validation = { valid: boolean; errors: string[]; sessions?: number;
                           summary?: Record<string, number> };

/** Check a pasted dataset without storing it. Always resolves: errors are the answer. */
export const validateDataset = (dataset: unknown) =>
  post<Validation>('/datasets/validate', { dataset });

/** Store a pasted dataset for this session and return the id to run it under. */
export async function uploadDataset(dataset: unknown) {
  const response = await fetch(`${API}/datasets`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ dataset }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((body?.detail?.errors ?? ['Could not store dataset']).join('; '));
  }
  return body as { dataset_id: string; name: string; sessions: number };
}

export const getRun = (id: string) => request<Run>(`/runs/${id}`);

export const startRun = (body: Record<string, unknown>) =>
  post<{ run_id: string; status: string; max_evaluations: number }>('/runs', body);

export const cancelRun = (id: string) => post<{ status: string }>(`/runs/${id}/cancel`, {});

export const startComparison = (body: Record<string, unknown>) =>
  post<Comparison>('/comparisons', body);

export const getComparison = (id: string) => request<Comparison>(`/comparisons/${id}`);

export const startExperiment = (body: Record<string, unknown>) =>
  post<Experiment>('/experiments', body);

export const getExperiment = (id: string) => request<Experiment>(`/experiments/${id}`);

/** Score a hand-edited timetable with the same evaluator the optimizers use. */
export const evaluateSchedule = (datasetId: string, schedule: Schedule) =>
  post<{ score: Score; schedule: Schedule }>('/schedule/evaluate',
    { dataset_id: datasetId, schedule });

/** Run every strategy on one shared budget and resolve when they have all finished. */
export async function raceAll(datasetId: string, maxEvaluations: number, seed = 42,
                              parameters: Record<string, number> = {}): Promise<Comparison> {
  const created = await startComparison({
    dataset_id: datasetId, seed, max_evaluations: maxEvaluations, parameters,
  });
  while (true) {
    const current = await getComparison(created.comparison_id);
    if (current.status === 'completed') return current;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
}
