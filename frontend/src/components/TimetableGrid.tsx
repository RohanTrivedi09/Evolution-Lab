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
export function TimetableGrid({ dataset, schedule, scope, animate = true, onSelect, selected }: {
  dataset: Dataset | null;
  schedule: Schedule;
  /** Namespaces chip keys so several grids can be mounted at once. */
  scope: string;
  animate?: boolean;
  onSelect?: (sessionId: string) => void;
  selected?: string | null;
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
  const Chip = animate ? motion.button : 'button';
  // Chips settle in place rather than flying between cells: while a scene is being
  // scrubbed the schedule can change many times a second, and shared-layout projection
  // never settles under that, leaving chips mid-flight across cell boundaries.
  const enter = animate
    ? { initial: { opacity: 0, scale: 0.94 }, animate: { opacity: 1, scale: 1 },
        transition: { duration: 0.16, ease: 'easeOut' } }
    : {};

  return (
    <div className="week-grid" style={{ gridTemplateColumns: `64px repeat(${dataset.days.length}, minmax(0, 1fr))` }}>
      <div className="week-corner" />
      {dataset.days.map(day => <div className="week-day" key={day}>{day}</div>)}
      {dataset.periods.map(period => (
        <React.Fragment key={period}>
          <div className="week-period">{period}</div>
          {dataset.days.map(day => {
            const entries = cells.get(`${day}|${period}`) ?? [];
            return (
              <div className={`week-cell${entries.length ? ' occupied' : ''}`} key={`${day}-${period}`}>
                {entries.map(entry => (
                  <Chip
                    {...enter}
                    key={`${scope}:${entry.id}:${day}:${period}`}
                    type="button"
                    className={`chip${entry.clash ? ' clash' : ''}${selected === entry.id ? ' selected' : ''}`}
                    onClick={onSelect ? () => onSelect(entry.id) : undefined}
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
