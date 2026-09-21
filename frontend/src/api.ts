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
  /** pending = signed up, waiting for the council; the engine skips them */
  status: "pending" | "active";
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
  requires_confirmation?: boolean;
  can_save?: boolean;
  confirmation_message?: string | null;
  /** gaps the parser filled in (no day named, only a start time) — shown before saving */
  assumptions: string[];
};

export type AssistantResponse = {
  transcript: string;
  language: string;
  intent: string;
  entities: Record<string, unknown>;
  confidence: number;
  requires_confirmation: boolean;
  confirmation_message: string | null;
  action_preview: Record<string, unknown>;
  reply: string;
  result: unknown;
};

export type WorkerSummary = {
  worker_id: number;
  status: "pending" | "active";
  jobs_this_week: number;
  completed_jobs: number;
  share_rupees: number;
  share_this_month_rupees: number;
  billed_this_month_rupees: number;
  rating: number | null;
  rating_count: number;
  engagement_days: number;
  days_to_benefits: number;
  eligibility_days: number;
  free_hours_this_week: number;
  awaiting_reply: number;
  split_percent: { worker: number; welfare_fund: number; platform_operations: number };
};

export type JobOutcome = "assigned" | "accepted" | "completed" | "declined";

export type WorkerJob = {
  booking_id: number;
  customer_name: string;
  customer_phone: string | null;
  trade: string;
  address: string | null;
  latitude: number;
  longitude: number;
  scheduled_for: string | null;
  outcome: JobOutcome;
  assigned_at: string | null;
  accepted_at: string | null;
  start_selfie_url: string | null;
  started_at: string | null;
  end_photo_url: string | null;
  completed_at: string | null;
  explanation: string | null;
  billed_rupees: number | null;
  share_rupees: number | null;
  rating: number | null;
  rating_comment: string | null;
  decline_reason: DeclineReason | null;
  declined_at: string | null;
  /** The price on the table once the worker has proposed one (status, amounts, whose turn) */
  settlement: SettlementBrief | null;
};

// ── Pricing: community rate card and the price agreed at the end of a job ─

export type Rate = {
  trade: string;
  visit_charge_rupees: number;
  hourly_rate_rupees: number;
  min_hours: number;
  band_percent: number;
  note: string | null;
  updated_at: string | null;
  typical_hours: number | null;
};

export type RateUpdate = Partial<Pick<Rate, "visit_charge_rupees" | "hourly_rate_rupees" | "min_hours" | "band_percent" | "note">>;

export type Quote = {
  trade: string;
  hours_worked: number;
  billable_hours: number;
  visit_charge_rupees: number;
  hourly_rate_rupees: number;
  labour_rupees: number;
  materials_rupees: number;
  standard_rupees: number;
  band_percent: number;
  min_fair_rupees: number;
  max_fair_rupees: number;
  typical_hours: number | null;
  explanation: string;
};

export type SettlementStatus = "proposed" | "countered" | "agreed" | "disputed";
export type PaidVia = "cash" | "upi" | "other";

export type SettlementBrief = {
  status: SettlementStatus;
  hours_worked: number;
  materials_rupees: number;
  standard_rupees: number;
  proposed_rupees: number;
  counter_rupees: number | null;
  agreed_rupees: number | null;
  customer_note: string | null;
  paid_via: PaidVia | null;
  dispute_id: number | null;
  waiting_on: "customer" | "worker" | "council" | null;
};

export type Settlement = SettlementBrief & {
  id: number;
  booking_id: number;
  worker_id: number;
  worker_name: string | null;
  customer_name: string | null;
  trade: string;
  work_note: string | null;
  min_fair_rupees: number;
  max_fair_rupees: number;
  created_at: string;
  responded_at: string | null;
  agreed_at: string | null;
  explanation: string;
  ledger: LedgerEntry[];
};

export type SettlementPropose = { hours_worked: number; materials_rupees?: number; work_note?: string | null; amount_rupees?: number | null };
export type SettlementRespond = { action: "agree" | "counter" | "dispute"; amount_rupees?: number | null; note?: string | null; paid_via?: PaidVia | null };

/** One change on the server, published to every signed-in client (see lib/live.ts). */
export type LiveEvent = {
  seq: number;
  at: string;
  topic: "bookings" | "settlements" | "disputes" | "workers" | "rates" | "cooperative" | "allocation";
  action: string;
  booking_id: number | null;
  worker_id: number | null;
  dispute_id: number | null;
};

export type DeclineReason = "unwell" | "too_far" | "already_booked" | "not_my_job" | "other";

export type ReplyResult = { booking_id: number; status: string; reassigned_to: string | null };

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
    worker: Record<string, unknown> & {
      id: number;
      name: string;
      trade: string;
      jobs_this_week: number;
      rating: number | null;
      latitude?: number;
      longitude?: number;
      phone?: string | null;
    };
    score: number | null;
    score_breakdown: Record<string, number> | null;
    explanation: string | null;
    assigned_at: string | null;
    accepted_at?: string | null;
    start_selfie_url?: string | null;
    started_at?: string | null;
    end_photo_url?: string | null;
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
  forecast_jobs?: number | null;
  confidence: number;
  explanation: string;
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

// ── Sabha: cooperative profile, overview, disputes ─────────────────────

export type Cooperative = {
  name: string;
  short_name: string;
  registration_id: string | null;
  established: number | null;
  area: string | null;
  radius_km: number | null;
  verified: boolean;
  worker_kyc: boolean;
  payments_verified: boolean;
  secretary: string | null;
  coordinator: string | null;
  last_meeting: string | null;
  weekly_job_limit: number;
  fund_allocation: Record<string, number>;
  updated_at: string | null;
};

export type CooperativeUpdate = Partial<Omit<Cooperative, "updated_at">>;

export type Dispute = {
  id: number;
  booking_id: number;
  kind: "payment" | "quality" | "other";
  label: string;
  raised_by: "customer" | "worker" | "council";
  raised_by_user_id: number | null;
  raised_by_name: string | null;
  amount_rupees: number | null;
  description: string | null;
  status: "open" | "resolved";
  resolution: string | null;
  created_at: string;
  resolved_at: string | null;
  trade: string | null;
  customer_name: string | null;
  worker_name: string | null;
  settlement_status: SettlementStatus | null;
  settlement_standard_rupees: number | null;
  settlement_proposed_rupees: number | null;
  settlement_counter_rupees: number | null;
};

export type AttentionItem = { level: "red" | "amber" | "green"; kind: "assign" | "disputes" | "workload" | "settle" | "opportunity"; count: number; text: string; action: string; trade: string | null };
export type TradeRow = { trade: string; demand: number; unassigned: number; ongoing: number; available_workers: number; status: "good" | "moderate" | "needs_workers" | "idle" };
export type Suggestion = { worker_id: number; name: string; distance_km: number; rating: number | null; availability: "available" | "unavailable" | "unknown"; jobs_this_week: number; score: number; explanation: string };
export type MatchingGroup = { trade: string; unassigned: number; booking_id: number; booking_age_minutes: number; suggestions: Suggestion[] };
export type WorkloadRow = { worker_id: number; name: string; trade: string; jobs_this_week: number; limit: number; pct: number; flag: "overloaded" | "under_utilised" | null };

export type Overview = {
  generated_at: string;
  cooperative: { name: string; short_name: string; verified: boolean; members: number; active_workers: number; categories: number };
  profile: Cooperative;
  metrics: {
    demands: { active: number; unassigned: number; ongoing: number; completed_today: number };
    workers: { active: number; registered: number; available_now: number };
    earnings: { this_month_rupees: number; last_month_rupees: number; change_pct: number | null };
    fairness: { index: number; workload: number; pay: number; allocation: number };
    fund: { total_rupees: number; this_month_rupees: number; allocation: Record<string, number> };
  };
  attention: AttentionItem[];
  trades: TradeRow[];
  matching: MatchingGroup[];
  network: { registered: number; active: number; available: number; offline: number; limit: number; workload: WorkloadRow[] };
  performance: { jobs_completed: number; workers_benefited: number; avg_worker_earnings_month_rupees: number; repeat_customers_pct: number | null; disputes_resolved_pct: number | null; avg_response_minutes: number | null };
  disputes: { open: number; resolved: number; resolution_rate: number | null; recent: Dispute[] };
  forecast_insight: { trade: string | null; peak_day: string | null; peak_weekday: string | null; expected_bookings: number; workers_needed: number; available_workers: number; shortage: number; text: string };
};

export type CustomerRow = { id: number; name: string; phone: string; locality: string | null; bookings: number; completed: number; last_booking_at: string | null; joined_at: string | null };

export type AutoAllocation = {
  trade: string | null;
  attempted: number;
  assigned: { booking_id: number; worker_id: number; worker_name: string | null; score: number; explanation: string }[];
  skipped: { booking_id: number; reason: string }[];
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
  forecast_jobs?: number | null;
  confidence: number;
  explanation: string;
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
  confidence: number;
  explanation: string;
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

export function storageRemove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

/** Public API origin when the SPA is hosted separately (Cloudflare Pages). Empty = same origin. */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const SESSION_TOKEN_KEY = "sahakarsetu_session_token";

export function getSessionToken(): string | null {
  return storageGet(SESSION_TOKEN_KEY);
}

export function setSessionToken(token: string | null): void {
  if (token) storageSet(SESSION_TOKEN_KEY, token);
  else storageRemove(SESSION_TOKEN_KEY);
}

export type AuthStatus = {
  user: User | null;
  access_role?: string | null;
  session_token?: string | null;
};

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const targetUrl = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  const token = getSessionToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let response: Response;
  try {
    response = await fetch(targetUrl, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      credentials: "include",
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
const put = <T>(path: string, body: unknown) => request<T>("PUT", path, body);
const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
const del = <T>(path: string) => request<T>("DELETE", path);

async function authPost(path: string, body?: unknown): Promise<AuthStatus> {
  const status = await post<AuthStatus>(path, body ?? {});
  if (status.session_token) setSessionToken(status.session_token);
  return status;
}

export const api = {
  auth: {
    me: () => get<AuthStatus>("/auth/me"),
    signup: (body: SignupBody) => authPost("/auth/signup", body),
    login: (portal: PortalId, phone: string, password: string) =>
      authPost("/auth/login", { portal, phone, password }),
    logout: async () => {
      try {
        return await post<AuthStatus>("/auth/logout");
      } finally {
        setSessionToken(null);
      }
    },
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
  assistant: {
    message: (body: { transcript: string; confirmed?: boolean; reference_date?: string | null; latitude?: number; longitude?: number }) =>
      post<AssistantResponse>("/assistant/message", body),
    voice: (body: { transcript: string; confirmed?: boolean; reference_date?: string | null; latitude?: number; longitude?: number }) =>
      post<AssistantResponse>("/assistant/voice", body),
    parseQuery: (query: string, language = "hi") =>
      post<{ trade: string; urgency: string; preferred_time: string | null; notes: string; source: string; confidence: number }>(
        "/assistant/parse-query",
        { query, language }
      ),
    languages: () => get<{ code: string; name: string }[]>("/assistant/languages"),
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
    cancel: (id: number) => post<{ booking_id: number; status: string }>(`/bookings/${id}/cancel`),
  },
  kaam: {
    summary: () => get<WorkerSummary>("/workers/me/summary"),
    jobs: () => get<WorkerJob[]>("/workers/me/jobs"),
    accept: (bookingId: number) => post<ReplyResult>(`/bookings/${bookingId}/accept`),
    decline: (bookingId: number, reason: DeclineReason, markBusyToday = false, note?: string) =>
      post<ReplyResult>(`/bookings/${bookingId}/decline`, { reason, mark_busy_today: markBusyToday, note: note || null }),
    verifyArrival: (bookingId: number, photo_data_uri: string, latitude: number, longitude: number, timestamp: string) =>
      post<{ status: string }>(`/bookings/${bookingId}/verify-arrival`, { photo_data_uri, latitude, longitude, timestamp }),
    startWork: (bookingId: number, timestamp: string) =>
      post<{ status: string }>(`/bookings/${bookingId}/start-work`, { timestamp }),
    verifyCompletion: (bookingId: number, photo_data_uri: string, latitude: number, longitude: number, timestamp: string) =>
      post<{ status: string }>(`/bookings/${bookingId}/verify-completion`, { photo_data_uri, latitude, longitude, timestamp }),
    replaceAvailability: (workerId: number, windows: AvailabilityWindow[]) =>
      put<Worker>(`/workers/${workerId}/availability`, { windows }),
    patchWindow: (workerId: number, index: number, change: Partial<Pick<AvailabilityWindow, "start" | "end" | "available">>) =>
      patch<Worker>(`/workers/${workerId}/availability/${index}`, change),
    removeWindow: (workerId: number, index: number) => del<Worker>(`/workers/${workerId}/availability/${index}`),
    pending: () => get<Worker[]>("/workers/pending"),
    approve: (workerId: number) => post<Worker>(`/workers/${workerId}/approve`),
  },
  admin: {
    dashboard: () => get<Dashboard>("/admin/dashboard"),
    overview: () => get<Overview>("/admin/overview"),
    customers: () => get<CustomerRow[]>("/admin/customers"),
  },
  cooperative: {
    get: () => get<Cooperative>("/cooperative"),
    update: (body: CooperativeUpdate) => put<Cooperative>("/cooperative", body),
  },
  allocation: {
    auto: (trade?: string, limit = 20) => post<AutoAllocation>(`/allocation/auto?limit=${limit}${trade ? `&trade=${encodeURIComponent(trade)}` : ""}`),
    batchDispatch: (maxDistanceKm = 15.0) => post<{
      matched_count: number;
      assignments: Array<{
        booking_id: number;
        customer_name: string;
        worker_id: number;
        worker_name: string;
        trade: string;
        score: number;
        distance_km: number;
        explanation: string;
      }>;
      unassigned_bookings: number[];
      idle_workers: number[];
      solver: string;
      cooperative_fairness_summary: string;
    }>(`/allocation/batch-dispatch?max_distance_km=${maxDistanceKm}`),
  },
  disputes: {
    list: (status?: "open" | "resolved") => get<Dispute[]>(`/disputes${status ? `?status=${status}` : ""}`),
    raise: (body: { booking_id: number; kind: Dispute["kind"]; description?: string | null; amount_rupees?: number | null }) => post<Dispute>("/disputes", body),
    resolve: (id: number, resolution: string) => post<Dispute>(`/disputes/${id}/resolve`, { resolution }),
    getAIRecommendation: (disputeId: number) => get<{
      settlement_breakdown: {
        worker_proposed_inr: number;
        customer_counter_inr: number;
        materials_cost_inr: number;
        suggested_settlement_inr: number;
        worker_concession_inr: number;
        customer_concession_inr: number;
      };
      recommended_resolution_note: string;
      recommended_resolution_hindi: string;
      source: string;
    }>(`/disputes/${disputeId}/ai-recommendation`),
    analyzeSentiment: (text: string) => post<{
      text: string;
      polarity: number;
      label: "positive" | "neutral" | "negative";
      requires_council_review: boolean;
      engine: string;
    }>("/reviews/analyze-sentiment", { text }),
  },
  rates: {
    list: () => get<Rate[]>("/rates"),
    quote: (trade: string, hours: number, materials = 0) =>
      get<Quote>(`/rates/quote?trade=${encodeURIComponent(trade)}&hours=${hours}&materials=${materials}`),
    update: (trade: string, body: RateUpdate) => put<Rate>(`/rates/${encodeURIComponent(trade)}`, body),
  },
  settlement: {
    get: (bookingId: number) => get<Settlement | null>(`/bookings/${bookingId}/settlement`),
    propose: (bookingId: number, body: SettlementPropose) => post<Settlement>(`/bookings/${bookingId}/settlement`, body),
    respond: (bookingId: number, body: SettlementRespond) => post<Settlement>(`/bookings/${bookingId}/settlement/respond`, body),
    resolve: (bookingId: number, amount_rupees: number, resolution: string) =>
      post<Settlement>(`/bookings/${bookingId}/settlement/resolve`, { amount_rupees, resolution }),
    list: (status?: SettlementStatus | "open") => get<Settlement[]>(`/settlements${status ? `?status=${status}` : ""}`),
  },
  events: (after = 0) => get<LiveEvent[]>(`/events?after=${after}`),
  stats: () => get<PublicStats>("/stats"),
  staffing: (trade: string, days = 7, area?: string) =>
    get<StaffingForecast>(`/forecast/staffing?trade=${encodeURIComponent(trade)}&days=${days}${area ? `&area=${encodeURIComponent(area)}` : ""}`),
  forecast: (trade?: string, days = 7) =>
    get<Forecast>(`/forecast?days=${days}${trade ? `&trade=${encodeURIComponent(trade)}` : ""}`),
  forecastML: (trade = "general", wardId = "1") =>
    get<{
      trade: string;
      ward_id: string | number;
      model_type: string;
      total_7d_predicted_bookings: number;
      daily_forecast: Array<{
        date: string;
        day_name: string;
        is_weekend: boolean;
        predicted_bookings: number;
        floor_rate_inr: number;
        recommended_rate_inr: number;
      }>;
      insights: string;
    }>(`/forecast/ml?trade=${encodeURIComponent(trade)}&ward_id=${encodeURIComponent(wardId)}`),
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
