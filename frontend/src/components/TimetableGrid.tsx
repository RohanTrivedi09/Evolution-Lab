import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import type { Dataset, Schedule } from '../types';

/**
 * A week grid that shows every session sharing a slot, not just the first one.
 *
 * Two sessions can legitimately share a day and period in different rooms, and two in
 * the *same* room is precisely the clash the tool exists to reveal. Rendering one
 * session per cell hides both cases, so cells hold a list and same-room collisions are
 * marked with a badge rather than by colour alone.
 */
export function TimetableGrid({ dataset, schedule, scope, animate = true, onSelect, selected, onMove }: {
  dataset: Dataset | null;
  schedule: Schedule;
  /** Namespaces chip keys so several grids can be mounted at once. */
  scope: string;
  animate?: boolean;
  onSelect?: (sessionId: string) => void;
  selected?: string | null;
  /** Supplying this makes the grid editable: chips can be dragged, or moved with the
   *  arrow keys once focused. Drag alone would leave the grid unusable by keyboard. */
  onMove?: (sessionId: string, day: string, period: string) => void;
}) {
  const cells = useMemo(() => {
    const map = new Map<string, { id: string; room: string; clash: boolean }[]>();
    for (const [id, slot] of Object.entries(schedule)) {
      const key = `${slot.day}|${slot.period}`;
      const bucket = map.get(key) ?? [];
      bucket.push({ id, room: slot.room_id, clash: false });
      map.set(key, bucket);
    }
    for (const bucket of map.values()) {
      const perRoom = new Map<string, number>();
      for (const entry of bucket) perRoom.set(entry.room, (perRoom.get(entry.room) ?? 0) + 1);
      for (const entry of bucket) entry.clash = (perRoom.get(entry.room) ?? 0) > 1;
    }
    return map;
  }, [schedule]);

  if (!dataset) return null;
  const Chip: React.ElementType = animate && !onMove ? motion.button : 'button';

  const nudge = (event: React.KeyboardEvent, id: string, day: string, period: string) => {
    const keys: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1],
    };
    const delta = keys[event.key];
    if (!delta || !onMove) return;
    event.preventDefault();
    const clamp = (v: number, max: number) => Math.min(max, Math.max(0, v));
    const dayIndex = clamp(dataset.days.indexOf(day) + delta[0], dataset.days.length - 1);
    const periodIndex = clamp(dataset.periods.indexOf(period) + delta[1], dataset.periods.length - 1);
    onMove(id, dataset.days[dayIndex], dataset.periods[periodIndex]);
  };
  // Chips settle in place rather than flying between cells: while a scene is being
  // scrubbed the schedule can change many times a second, and shared-layout projection
  // never settles under that, leaving chips mid-flight across cell boundaries.
  const enter = animate && !onMove
    ? { initial: { opacity: 0, scale: 0.94 }, animate: { opacity: 1, scale: 1 },
        transition: { duration: 0.16, ease: 'easeOut' } }
    : {};

  return (
    <div className="week-grid" style={{ gridTemplateColumns: `64px repeat(${dataset.days.length}, minmax(0, 1fr))`, ['--days' as string]: dataset.days.length }}>
      <div className="week-corner" />
      {dataset.days.map(day => <div className="week-day" key={day}>{day}</div>)}
      {dataset.periods.map(period => (
        <React.Fragment key={period}>
          <div className="week-period">{period}</div>
          {dataset.days.map(day => {
            const entries = cells.get(`${day}|${period}`) ?? [];
            return (
              <div
                className={`week-cell${entries.length ? ' occupied' : ''}${onMove ? ' droppable' : ''}`}
                key={`${day}-${period}`}
                onDragOver={onMove ? event => event.preventDefault() : undefined}
                onDrop={onMove ? event => {
                  event.preventDefault();
                  const id = event.dataTransfer.getData('text/plain');
                  if (id) onMove(id, day, period);
                } : undefined}
              >
                {entries.map(entry => (
                  <Chip
                    {...enter}
                    key={`${scope}:${entry.id}:${day}:${period}`}
                    type="button"
                    className={`chip${entry.clash ? ' clash' : ''}${selected === entry.id ? ' selected' : ''}${onMove ? ' movable' : ''}`}
                    onClick={onSelect ? () => onSelect(entry.id) : undefined}
                    draggable={!!onMove}
                    onDragStart={onMove ? (event: React.DragEvent) =>
                      event.dataTransfer.setData('text/plain', entry.id) : undefined}
                    onKeyDown={onMove ? (event: React.KeyboardEvent) =>
                      nudge(event, entry.id, day, period) : undefined}
                    title={`${entry.id} in ${entry.room}${entry.clash ? ' - room double-booked' : ''}`}
                  >
                    <b>{entry.id}</b>
                    <small>{entry.room}</small>
                    {entry.clash && <span className="clash-badge" aria-label="room double-booked">!</span>}
                  </Chip>
                ))}
              </div>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
}
