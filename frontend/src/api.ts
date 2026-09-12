/**
 * Typed client for the SahakarSetu API (app/main.py + app/routers/booking_flow.py).
 * Paths are root-relative: in dev Vite proxies them to :8000, in production
 * FastAPI serves both the API and this app.
 */

export type AvailabilityWindow = {
  date: string | null;
  weekday: number | null;
  start: string;
  end: string;
  available: boolean;
};

export type Worker = {
  id: number;
  name: string;
  trade: string;
  latitude: number;
  longitude: number;
  phone: string | null;
  rating: number | null;
  availability: AvailabilityWindow[];
  jobs_this_week: number;
  created_at: string | null;
};

export type Booking = {
  id: number;
  customer_name: string;
  trade: string;
  latitude: number;
  longitude: number;
  scheduled_for: string | null;
  customer_phone: string | null;
  address: string | null;
  status: "pending" | "assigned" | "completed" | string;
  created_at: string | null;
};

export type BookingCreate = {
  customer_name: string;
  trade: string;
  latitude: number;
  longitude: number;
  scheduled_for?: string | null;
  customer_phone?: string | null;
  address?: string | null;
};

export type Recommendation = {
  rank: number;
  worker_id: number;
  worker_name: string;
  distance_km: number;
  score: number;
  score_breakdown: Record<string, number>;
  explanation: string;
  why_selected: string[];
};

export type VoiceParse = {
  transcript: string;
  language: "hi" | "en" | "mixed" | "unknown";
  windows: AvailabilityWindow[];
  confidence: number;
  summary: string;
  unrecognised: string[];
  requires_confirmation: boolean;
  can_save: boolean;
  confirmation_message: string | null;
};

export type LedgerEntry = {
  party: "worker" | "welfare_fund" | "platform_operations";
  share_percent: number;
  amount_paise: number;
  amount_rupees: number;
  worker_id: number | null;
};

export type BookingDetail = {
  booking: Booking & Record<string, unknown>;
  assignment: {
    assignment_id: number;
    worker: Record<string, unknown> & { id: number; name: string; trade: string; jobs_this_week: number; rating: number | null };
    score: number | null;
    score_breakdown: Record<string, number> | null;
    explanation: string | null;
    assigned_at: string | null;
  } | null;
  payment_ledger: LedgerEntry[];
  rating: { rating: number; comment: string | null; created_at: string } | null;
};

export type AssignmentResult = {
  booking_id: number;
  status: string;
  assignment_id: number;
  worker: Record<string, unknown> & { id: number; name: string };
  score: number;
  score_breakdown: Record<string, number>;
  explanation: string;
};

export type CompletionResult = {
  booking_id: number;
  status: string;
  worker_id: number;
  amount_rupees: number;
  ledger: LedgerEntry[];
};

export type RatingResult = {
  booking_id: number;
  worker_id: number;
  rating: number;
  worker_average_rating: number | null;
  worker_rating_count: number;
};

export type DashboardWorker = {
  id: number;
  name: string | null;
  jobs_this_week: number;
  rating: number | null;
  completed_jobs: number;
  earnings_rupees: number;
  engagement_days: number;
  days_to_social_security_eligibility: number;
};

export type Dashboard = {
  bookings: { total: number; pending: number; assigned: number; completed: number };
  money: { gross_rupees: number; worker_payouts_rupees: number; welfare_fund_rupees: number; platform_operations_rupees: number };
  ratings: { count: number; average: number | null };
  fairness: { jobs_this_week_min: number; jobs_this_week_max: number; jobs_this_week_mean: number; jobs_gini: number; workers_with_no_jobs_this_week: number };
  workers: DashboardWorker[];
  recent_assignments: { assignment_id: number; booking_id: number; worker_id: number; score: number | null; booking_status: string; worker_name: string | null }[];
};

export type ForecastPoint = {
  date: string;
  weekday: string;
  already_booked: number;
  expected_bookings: number;
  lower: number;
  upper: number;
  workers_needed: number;
};

export type Forecast = {
  trade: string | null;
  horizon_days: number;
  history_days: number;
  history_bookings: number;
  method: string;
  total_expected: number;
  points: ForecastPoint[];
};

export type PublicStats = {
  workers: number;
  bookings_completed: number;
  welfare_fund_rupees: number;
  average_rating: number | null;
};

export type StaffingDay = {
  date: string;
  weekday: string;
  expected_bookings: number;
  workers_needed: number;
  available_workers: number;
  shortage: number;
};

export type StaffingForecast = {
  trade: string;
  area: string | null;
  horizon_days: number;
  peak_day: string | null;
  expected_bookings: number;
  workers_needed: number;
  available_workers: number;
  shortage: number;
  recommendation: string;
  days: StaffingDay[];
};

export type PortalId = "ghar" | "kaam" | "sabha";

export type User = {
  id: number;
  portal: PortalId;
  name: string;
  phone: string;
  locality: string | null;
  role: string | null;
  worker_id: number | null;
  languages: string[];
  created_at: string | null;
};

export type SignupBody = {
  portal: PortalId;
  name: string;
  phone: string;
  password: string;
  locality?: string | null;
  trade?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  languages?: string[];
  role?: string | null;
  council_code?: string | null;
};

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

const REQUEST_TIMEOUT_MS = 15000;

export function storageGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function storageSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private browsing and storage quotas should not make the app unusable.
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? undefined : { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    const message = error instanceof DOMException && error.name === "AbortError"
      ? "The server took too long to respond. Please try again."
      : "Unable to reach the server. Check your connection and try again.";
    throw new ApiError(0, message);
  } finally {
    window.clearTimeout(timeout);
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }

    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {});

export const api = {
  auth: {
    me: () => get<{ user: User | null }>("/auth/me"),
    signup: (body: SignupBody) => post<{ user: User }>("/auth/signup", body),
    login: (portal: PortalId, phone: string, password: string) => post<{ user: User }>("/auth/login", { portal, phone, password }),
    logout: () => post<{ user: null }>("/auth/logout"),
  },
  workers: {
    list: (trade?: string) => get<Worker[]>(`/workers${trade ? `?trade=${encodeURIComponent(trade)}` : ""}`),
    get: (id: number) => get<Worker>(`/workers/${id}`),
    create: (body: Omit<Worker, "id" | "jobs_this_week" | "created_at" | "availability" | "phone" | "rating"> & Partial<Worker>) =>
      post<Worker>("/workers", body),
    setAvailabilityByVoice: (id: number, transcript: string, replace = true, referenceDate?: string, confirmed = false) =>
      post<{ parsed: VoiceParse; worker: Worker }>(`/workers/${id}/availability/voice`, {
        transcript,
        replace,
        reference_date: referenceDate ?? null,
        confirmed,
      }),
  },
  voice: {
    parse: (transcript: string, referenceDate?: string) =>
      post<VoiceParse>("/voice/parse", { transcript, reference_date: referenceDate ?? null }),
  },
  bookings: {
    list: (params: { status?: string; trade?: string } = {}) => {
      const query = new URLSearchParams();
      if (params.status) query.set("status", params.status);
      if (params.trade) query.set("trade", params.trade);
      const suffix = query.toString();
      return get<Booking[]>(`/bookings${suffix ? `?${suffix}` : ""}`);
    },
    create: (body: BookingCreate) => post<Booking>("/bookings", body),
    detail: (id: number) => get<BookingDetail>(`/bookings/${id}`),
    recommendations: (id: number, topK = 3) => get<Recommendation[]>(`/bookings/${id}/recommendations?top_k=${topK}`),
    assign: (id: number) => post<AssignmentResult>(`/bookings/${id}/assign`),
    complete: (id: number, amount: number) => post<CompletionResult>(`/bookings/${id}/complete`, { amount }),
    rate: (id: number, rating: number, comment?: string) =>
      post<RatingResult>(`/bookings/${id}/rating`, { rating, comment: comment || null }),
  },
  admin: {
    dashboard: () => get<Dashboard>("/admin/dashboard"),
  },
  stats: () => get<PublicStats>("/stats"),
  staffing: (trade: string, days = 7, area?: string) =>
    get<StaffingForecast>(`/forecast/staffing?trade=${encodeURIComponent(trade)}&days=${days}${area ? `&area=${encodeURIComponent(area)}` : ""}`),
  forecast: (trade?: string, days = 7) =>
    get<Forecast>(`/forecast?days=${days}${trade ? `&trade=${encodeURIComponent(trade)}` : ""}`),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") return error.detail;
    if (error.detail && typeof error.detail === "object" && "message" in error.detail) {
      return String((error.detail as { message: unknown }).message);
    }
    if (Array.isArray(error.detail)) {
      return error.detail.map((e: { msg?: string }) => e.msg ?? "invalid input").join("; ");
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}

export const TRADES = ["plumbing", "electrical", "carpentry", "cleaning", "painting"] as const;

/** Where the cooperative operates; used until the browser gives a GPS fix. */
export const DEFAULT_LOCATION = { latitude: 23.18, longitude: 77.42, label: "Bhopal" };

export function titleCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatRupees(value: number): string {
  return "₹" + value.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export function formatWhen(iso: string | null): string {
  if (!iso) return "As soon as possible";
  const date = new Date(iso);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  const time = date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
  if (same(date, today)) return `Today ${time}`;
  if (same(date, tomorrow)) return `Tomorrow ${time}`;
  return `${date.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })} ${time}`;
}

export function describeWindow(w: AvailabilityWindow): string {
  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  let when = "every day";
  if (w.date) {
    const date = new Date(w.date + "T00:00");
    const today = new Date();
    const diff = Math.round((date.getTime() - new Date(today.toDateString()).getTime()) / 86_400_000);
    const relative = diff === 0 ? "today" : diff === 1 ? "tomorrow" : diff === 2 ? "day after tomorrow" : null;
    const pretty = date.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
    when = relative ? `${relative}, ${pretty}` : pretty;
  } else if (w.weekday !== null) {
    when = `every ${DAYS[w.weekday]}`;
  }
  return `${w.available ? "Free" : "Busy"} · ${when}`;
}
