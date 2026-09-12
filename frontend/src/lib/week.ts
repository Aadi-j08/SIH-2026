/**
 * The worker's week as three slots a day (morning / noon / evening), built from
 * the availability windows the voice parser wrote plus the jobs they hold.
 * Tapping a slot turns into one AvailabilityWindow for that day and slot.
 */
import type { AvailabilityWindow, WorkerJob } from "../api";

export type SlotId = "morning" | "noon" | "evening";
export type SlotState = "free" | "busy" | "job" | "unset";

export const SLOTS: { id: SlotId; label: string; hindi: string; start: string; end: string }[] = [
  { id: "morning", label: "Morning", hindi: "सुबह", start: "06:00", end: "12:00" },
  { id: "noon", label: "Noon", hindi: "दोपहर", start: "12:00", end: "17:00" },
  { id: "evening", label: "Evening", hindi: "शाम", start: "17:00", end: "21:00" },
];

export type DaySlot = {
  date: string;              // YYYY-MM-DD
  slot: SlotId;
  state: SlotState;
  /** indexes into worker.availability of the windows touching this slot */
  windows: number[];
  /** the job scheduled inside this slot, if any */
  job: WorkerJob | null;
  /** hours of the slot the worker is free (after busy windows) */
  freeHours: number;
};

export type WeekDay = {
  date: string;
  label: string;             // SAT
  dayNumber: number;         // 12
  isToday: boolean;
  slots: DaySlot[];
};

const DAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function minutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function appliesOn(w: AvailabilityWindow, date: string, weekday: number): boolean {
  if (w.date) return w.date === date;
  if (w.weekday !== null && w.weekday !== undefined) return w.weekday === weekday;
  return true;
}

/** Monday = 0 … Sunday = 6, matching the backend's Weekday. */
function weekdayOf(d: Date): number {
  return (d.getDay() + 6) % 7;
}

function overlapMinutes(aStart: string, aEnd: string, bStart: string, bEnd: string): number {
  const lo = Math.max(minutes(aStart), minutes(bStart));
  const hi = Math.min(minutes(aEnd), minutes(bEnd));
  return Math.max(0, hi - lo);
}

/** Build the next `days` days starting today. */
export function buildWeek(windows: AvailabilityWindow[], jobs: WorkerJob[], days = 7, today = new Date()): WeekDay[] {
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const week: WeekDay[] = [];
  for (let offset = 0; offset < days; offset += 1) {
    const d = new Date(start);
    d.setDate(start.getDate() + offset);
    const date = isoDate(d);
    const weekday = weekdayOf(d);
    const slots: DaySlot[] = SLOTS.map((slot) => {
      const slotLength = minutes(slot.end) - minutes(slot.start);
      const touching: number[] = [];
      let freeMinutes = 0;
      let busyMinutes = 0;
      windows.forEach((w, index) => {
        if (!appliesOn(w, date, weekday)) return;
        const overlap = overlapMinutes(w.start, w.end, slot.start, slot.end);
        if (overlap === 0) return;
        touching.push(index);
        if (w.available) freeMinutes += overlap;
        else busyMinutes += overlap;
      });
      const job = jobs.find((j) => {
        if (!j.scheduled_for || (j.outcome !== "assigned" && j.outcome !== "accepted")) return false;
        const when = new Date(j.scheduled_for);
        if (isoDate(when) !== date) return false;
        const t = when.getHours() * 60 + when.getMinutes();
        return t >= minutes(slot.start) && t < minutes(slot.end);
      }) ?? null;
      const free = Math.max(0, Math.min(slotLength, freeMinutes) - busyMinutes);
      let state: SlotState = "unset";
      if (job) state = "job";
      else if (busyMinutes > 0 && free === 0) state = "busy";
      else if (free > 0) state = "free";
      return { date, slot: slot.id, state, windows: touching, job, freeHours: Math.round((free / 60) * 10) / 10 };
    });
    week.push({ date, label: DAY_LABELS[weekday], dayNumber: d.getDate(), isToday: offset === 0, slots });
  }
  return week;
}

/** The window a tap on an empty slot creates. */
export function windowForSlot(date: string, slot: SlotId, available = true): AvailabilityWindow {
  const def = SLOTS.find((s) => s.id === slot)!;
  return { date, weekday: null, start: def.start, end: def.end, available };
}

export function formatDateLong(date: string): string {
  return new Date(date + "T00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

export function slotLabel(slot: SlotId): string {
  return SLOTS.find((s) => s.id === slot)!.label;
}
