/**
 * Live updates. One EventSource on /events/stream per page; when the server
 * publishes a change the page reloads what it shows (through the same
 * authorised endpoints it always used — the event carries no data). While
 * the stream is connected the caller can slow its polling right down; if
 * the browser cannot hold a stream, the hook falls back to GET /events.
 */
import { useEffect, useRef, useState } from "react";

import { api, API_BASE_URL, type LiveEvent } from "../api";

type Options = {
  /** Only events for which this returns true trigger `onEvent` (default: all). */
  filter?: (e: LiveEvent) => boolean;
  /** Collapse a burst of events into one call (ms). */
  debounceMs?: number;
  /** Fallback poll interval when the stream is down (ms). */
  pollMs?: number;
};

export function useLive(onEvent: (events: LiveEvent[]) => void, { filter, debounceMs = 400, pollMs = 8000 }: Options = {}): { live: boolean } {
  const [live, setLive] = useState(false);
  const handler = useRef(onEvent);
  const filterRef = useRef(filter);
  handler.current = onEvent;
  filterRef.current = filter;

  useEffect(() => {
    let last = 0;
    let pending: LiveEvent[] = [];
    let timer: number | null = null;
    let poll: number | null = null;
    let closed = false;

    const flush = () => {
      timer = null;
      const batch = pending;
      pending = [];
      if (batch.length) handler.current(batch);
    };
    const take = (events: LiveEvent[]) => {
      for (const e of events) {
        last = Math.max(last, e.seq);
        if (!filterRef.current || filterRef.current(e)) pending.push(e);
      }
      if (pending.length && timer === null) timer = window.setTimeout(flush, debounceMs);
    };

    const startPolling = () => {
      if (poll !== null || closed) return;
      poll = window.setInterval(async () => {
        try {
          take(await api.events(last));
        } catch {
          /* still down; keep trying */
        }
      }, pollMs);
    };
    const stopPolling = () => {
      if (poll !== null) window.clearInterval(poll);
      poll = null;
    };

    let source: EventSource | null = null;
    if ("EventSource" in window) {
      // Cross-origin Pages → API needs credentials so the session cookie is sent.
      // If third-party cookies are blocked, onerror falls back to Bearer polling.
      source = new EventSource(`${API_BASE_URL}/events/stream`, { withCredentials: true });
      source.onopen = () => {
        setLive(true);
        stopPolling();
      };
      source.onmessage = (m) => {
        try {
          take([JSON.parse(m.data) as LiveEvent]);
        } catch {
          /* not an event */
        }
      };
      source.onerror = () => {
        // The browser reconnects on its own; poll until it does.
        setLive(false);
        startPolling();
      };
    } else {
      startPolling();
    }

    return () => {
      closed = true;
      source?.close();
      stopPolling();
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [debounceMs, pollMs]);

  return { live };
}
