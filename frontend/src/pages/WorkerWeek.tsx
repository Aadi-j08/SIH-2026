import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, describeWindow, errorMessage, type Worker as WorkerT, type WorkerJob } from "../api";
import { ArrowLeft, Check, Clock, Cross, Mic } from "../components/Icons";
import { useAuth } from "../lib/auth";
import { buildWeek, formatDateLong, SLOTS, slotLabel, windowForSlot, type DaySlot } from "../lib/week";

/**
 * /kaam/week — the worker's schedule as the engine sees it. Seven days × three
 * slots; tap a slot to mark it free, busy, or remove what was said about it.
 */
export default function WorkerWeek() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [worker, setWorker] = useState<WorkerT | null>(null);
  const [jobs, setJobs] = useState<WorkerJob[]>([]);
  const [selected, setSelected] = useState<{ date: string; slot: DaySlot["slot"] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);

  const workerId = user?.worker_id ?? null;

  const load = useCallback(async () => {
    if (workerId === null) return;
    try {
      const [w, j] = await Promise.all([api.workers.get(workerId), api.kaam.jobs()]);
      setWorker(w);
      setJobs(j);
    } catch (e) {
      // Only show the error when no valid data is loaded yet (initial load).
      // Once the week grid is visible, transient failures should not destroy it.
      if (!worker) setMessage({ kind: "error", text: errorMessage(e) });
    }
  }, [workerId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const day = params.get("day");
    if (day && !selected) setSelected({ date: day, slot: "morning" });
  }, [params, selected]);

  if (workerId === null) return <div className="page notice error">This Kaam account is not linked to a worker record.</div>;
  if (!worker) return <div className="page muted">Loading…</div>;

  const week = buildWeek(worker.availability, jobs);
  const freeHours = week.reduce((sum, d) => sum + d.slots.reduce((s, x) => s + x.freeHours, 0), 0);
  const current = selected ? week.find((d) => d.date === selected.date)?.slots.find((s) => s.slot === selected.slot) ?? null : null;

  const apply = async (fn: () => Promise<WorkerT>, done: string) => {
    setBusy(true);
    setMessage(null);
    try {
      setWorker(await fn());
      setMessage({ kind: "info", text: done });
    } catch (e) {
      setMessage({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  /**
   * When removing day-specific windows that touch a slot, trim or split windows
   * that extend beyond the slot boundaries instead of deleting them entirely.
   * This preserves availability in adjacent slots (e.g. a 08:00–16:00 window
   * edited at the morning slot keeps the 12:00–16:00 portion for noon).
   */
  const trimWindowsForSlot = (slot: DaySlot) => {
    const slotDef = SLOTS.find((s) => s.id === slot.slot)!;
    const result: typeof worker.availability = [];
    worker.availability.forEach((w, i) => {
      if (!(slot.windows.includes(i) && w.date === slot.date)) {
        result.push(w);
        return;
      }
      // This day-specific window touches this slot — trim/split it.
      // Keep any portion before the slot starts.
      if (w.start < slotDef.start) {
        result.push({ ...w, end: slotDef.start });
      }
      // Keep any portion after the slot ends.
      if (w.end > slotDef.end) {
        result.push({ ...w, start: slotDef.end });
      }
      // The portion inside the slot is discarded.
    });
    return result;
  };

  /** Everything the worker said that touches this slot, replaced by one window for the slot. */
  const setSlot = (slot: DaySlot, available: boolean) => {
    const keep = trimWindowsForSlot(slot);
    return apply(
      () => api.kaam.replaceAvailability(worker.id, [...keep, windowForSlot(slot.date, slot.slot, available)]),
      `${formatDateLong(slot.date)} ${slotLabel(slot.slot).toLowerCase()} marked ${available ? "free" : "busy"}.`,
    );
  };

  /** Drop the day-specific windows for this slot; a recurring window stays (the sheet says so). */
  const clearSlot = (slot: DaySlot) => {
    const keep = trimWindowsForSlot(slot);
    return apply(() => api.kaam.replaceAvailability(worker.id, keep), "Removed.");
  };

  const removeWindow = (index: number) =>
    apply(() => api.kaam.removeWindow(worker.id, index), "Removed. The engine sees the change at once.");

  return (
    <div className="page" style={{ position: "relative" }}>
      <div className="row" style={{ gap: 12 }}>
        <Link to="/kaam/home" className="btn outline" style={{ width: 44, minHeight: 44, padding: 0 }} aria-label="Back to home">
          <ArrowLeft size={20} />
        </Link>
        <div className="stack grow" style={{ gap: 1 }}>
          <div className="display" style={{ fontSize: 20, fontWeight: 700 }}>My week</div>
          <div className="small muted">
            {formatDateLong(week[0].date)} – {formatDateLong(week[6].date)} · <span className="hi">मेरा हफ़्ता</span>
          </div>
        </div>
        <Link to="/kaam/home#voice" className="btn dark" style={{ minHeight: 40, padding: "0 12px", fontSize: 13, borderRadius: 999, gap: 6 }}>
          <Mic size={16} /> Speak
        </Link>
      </div>

      <div className="stack" style={{ gap: 6 }}>
        <div className="week-grid" style={{ alignItems: "end" }}>
          <div />
          {week.map((d) => (
            <div key={d.date} className={`dayhead${d.isToday ? " today" : ""}`}>
              <span className="dow">{d.label}</span>
              <span className="dnum">{d.dayNumber}</span>
            </div>
          ))}
        </div>
        {SLOTS.map((slotDef) => (
          <div className="week-grid" key={slotDef.id}>
            <div className="rowlabel">
              <b>{slotDef.label}</b>
              <small className="num">
                {slotDef.start.slice(0, 2)}–{slotDef.end.slice(0, 2)}
              </small>
            </div>
            {week.map((d) => {
              const s = d.slots.find((x) => x.slot === slotDef.id)!;
              const isSel = selected?.date === d.date && selected.slot === slotDef.id;
              return (
                <button
                  key={d.date}
                  type="button"
                  className={`slot ${s.state}${isSel ? " selected" : ""}`}
                  onClick={() => setSelected({ date: d.date, slot: slotDef.id })}
                  aria-label={`${d.label} ${d.dayNumber} ${slotDef.label}: ${s.state}`}
                >
                  {s.state === "job" && s.job ? (
                    <>
                      <span>{s.job.customer_name.split(" ")[0]}</span>
                      <small>{s.job.scheduled_for ? new Date(s.job.scheduled_for).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false }) : ""}</small>
                    </>
                  ) : s.state === "free" ? (
                    <span className="num">{s.freeHours < (slotDef.id === "evening" ? 4 : slotDef.id === "noon" ? 5 : 6) ? `${s.freeHours} h` : `${slotDef.start.slice(0, 2)}–${slotDef.end.slice(0, 2)}`}</span>
                  ) : s.state === "busy" ? (
                    <span>busy</span>
                  ) : null}
                </button>
              );
            })}
          </div>
        ))}
        <div className="legend" style={{ paddingTop: 2 }}>
          <span><i className="legend-swatch free" style={{ height: 10 }} />Free</span>
          <span><i className="legend-swatch" style={{ height: 10, backgroundImage: "repeating-linear-gradient(135deg, #8c857f 0 2px, #f7f3ec 2px 5px)" }} />Busy</span>
          <span><i className="legend-swatch job" style={{ height: 10, background: "var(--ink)" }} />Job</span>
          <span><i className="legend-swatch" style={{ height: 10, background: "var(--white)", border: "1.5px dashed var(--line)", boxSizing: "border-box" }} />Not set — tap to mark free</span>
        </div>
      </div>

      <div className="card soft row" style={{ gap: 12 }}>
        <Clock size={20} style={{ color: "var(--green-d)", flexShrink: 0 }} />
        <div className="small" style={{ color: "var(--ink-2)", lineHeight: 1.4 }}>
          <b style={{ color: "var(--ink)" }}>{freeHours} free hours</b> this week. The engine only offers you jobs inside green blocks.
        </div>
      </div>

      {message && <div className={`notice ${message.kind}`}>{message.text}</div>}

      {current && (
        <div className="sheet">
          <div className="row" style={{ gap: 12 }}>
            <span className={`dot ${current.state === "free" ? "green" : "grey"}`}>
              {current.state === "free" ? <Check size={16} /> : current.state === "busy" ? <Cross size={16} /> : <Clock size={16} />}
            </span>
            <div className="stack grow" style={{ gap: 1 }}>
              <div style={{ fontWeight: 700, color: current.state === "free" ? "var(--green-d)" : undefined }}>
                {current.state === "free" ? "Free" : current.state === "busy" ? "Busy" : current.state === "job" ? "Job" : "Not set"} · {formatDateLong(current.date)} {slotLabel(current.slot).toLowerCase()}
              </div>
              {current.state === "job" && current.job ? (
                <div className="small muted">{current.job.customer_name} · {current.job.address ?? ""}</div>
              ) : current.windows.length > 0 ? (
                <div className="small muted">
                  From: {current.windows.map((i) => `${describeWindow(worker.availability[i])} ${worker.availability[i].start}–${worker.availability[i].end}`).join("; ")}
                </div>
              ) : (
                <div className="small muted">You haven’t said anything about this slot yet.</div>
              )}
            </div>
            <button type="button" className="back" onClick={() => setSelected(null)} aria-label="Close">
              <Cross size={16} />
            </button>
          </div>
          {current.state !== "job" && (
            <div className="row" style={{ gap: 8 }}>
              {current.state !== "free" && (
                <button type="button" className="btn green grow" disabled={busy} onClick={() => setSlot(current, true)}>
                  Mark free
                </button>
              )}
              {current.state !== "busy" && (
                <button type="button" className="btn outline grow" disabled={busy} onClick={() => setSlot(current, false)}>
                  Mark busy
                </button>
              )}
              {current.windows.some((i) => worker.availability[i].date === current.date) && (
                <button type="button" className="btn danger" disabled={busy} onClick={() => clearSlot(current)}>
                  Remove
                </button>
              )}
            </div>
          )}
          {current.state !== "job" && current.windows.some((i) => worker.availability[i].date === null) && (
            <div className="stack" style={{ gap: 6 }}>
              <div className="tiny muted">This slot also comes from a repeating rule. Remove the rule to change every week:</div>
              {current.windows.filter((i) => worker.availability[i].date === null).map((i) => (
                <div key={i} className="row between small">
                  <span>{describeWindow(worker.availability[i])} · {worker.availability[i].start}–{worker.availability[i].end}</span>
                  <button type="button" className="btn small danger" disabled={busy} onClick={() => removeWindow(i)}>Remove rule</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {worker.availability.length > 0 && (
        <details className="card soft small">
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Everything saved ({worker.availability.length})</summary>
          <div className="stack" style={{ gap: 6, marginTop: 8 }}>
            {worker.availability.map((w, i) => (
              <div key={i} className="row between">
                <span>
                  {describeWindow(w)} <span className="num muted">{w.start} – {w.end}</span>
                </span>
                <button type="button" className="btn small outline" disabled={busy} onClick={() => removeWindow(i)}>Remove</button>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
