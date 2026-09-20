-- =============================================================================
-- SahakarSetu — PostgreSQL Schema (Neon.tech / Supabase / Render)
-- 100% Free Production Database Schema
-- =============================================================================

-- 1. Workers
CREATE TABLE IF NOT EXISTS workers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    trade           VARCHAR(100) NOT NULL,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    jobs_this_week  INTEGER NOT NULL DEFAULT 0 CHECK (jobs_this_week >= 0),
    rating          REAL CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    availability    TEXT NOT NULL DEFAULT '[]',
    status          VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active')),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Users (Authentication)
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    portal          VARCHAR(20) NOT NULL CHECK (portal IN ('ghar', 'kaam', 'sabha')),
    phone           VARCHAR(20) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    password_hash   TEXT NOT NULL,
    locality        VARCHAR(255),
    role            VARCHAR(100),
    worker_id       INTEGER REFERENCES workers(id) ON DELETE SET NULL,
    languages       TEXT NOT NULL DEFAULT '[]',
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_portal_phone UNIQUE (portal, phone)
);

-- 3. Sessions
CREATE TABLE IF NOT EXISTS sessions (
    token_hash      VARCHAR(255) PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL
);

-- 4. Bookings
CREATE TABLE IF NOT EXISTS bookings (
    id              SERIAL PRIMARY KEY,
    customer_name   VARCHAR(255) NOT NULL,
    customer_phone  VARCHAR(20),
    trade           VARCHAR(100) NOT NULL,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    address         TEXT,
    scheduled_for   VARCHAR(100),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'assigned', 'completed', 'cancelled')),
    customer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. Assignments
CREATE TABLE IF NOT EXISTS assignments (
    id              SERIAL PRIMARY KEY,
    booking_id      INTEGER NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,
    worker_id       INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    score           REAL,
    accepted_at     TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. Declines
CREATE TABLE IF NOT EXISTS declines (
    id              SERIAL PRIMARY KEY,
    booking_id      INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    worker_id       INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    reason          VARCHAR(50) NOT NULL CHECK (reason IN ('unwell', 'too_far', 'already_booked', 'not_my_job', 'other')),
    note            TEXT,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. Cooperative Info
CREATE TABLE IF NOT EXISTS cooperative (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    name              VARCHAR(255) NOT NULL,
    short_name        VARCHAR(100) NOT NULL,
    registration_id   VARCHAR(100),
    established       INTEGER,
    area              VARCHAR(255),
    radius_km         REAL,
    verified          INTEGER NOT NULL DEFAULT 0,
    worker_kyc        INTEGER NOT NULL DEFAULT 0,
    payments_verified INTEGER NOT NULL DEFAULT 0,
    secretary         VARCHAR(255),
    coordinator       VARCHAR(255),
    last_meeting      VARCHAR(50),
    weekly_job_limit  INTEGER NOT NULL DEFAULT 6 CHECK (weekly_job_limit > 0),
    fund_allocation   TEXT NOT NULL DEFAULT '{}',
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 8. Disputes
CREATE TABLE IF NOT EXISTS disputes (
    id                SERIAL PRIMARY KEY,
    booking_id        INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    kind              VARCHAR(20) NOT NULL CHECK (kind IN ('payment', 'quality', 'other')),
    raised_by         VARCHAR(20) NOT NULL CHECK (raised_by IN ('customer', 'worker', 'council')),
    raised_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    amount_paise      INTEGER CHECK (amount_paise IS NULL OR amount_paise >= 0),
    description       TEXT,
    status            VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    resolution        TEXT,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at       TIMESTAMP WITH TIME ZONE
);

-- 9. Standard Rate Card
CREATE TABLE IF NOT EXISTS standard_rates (
    trade              VARCHAR(100) PRIMARY KEY,
    visit_charge_paise INTEGER NOT NULL CHECK (visit_charge_paise >= 0),
    hourly_rate_paise  INTEGER NOT NULL CHECK (hourly_rate_paise > 0),
    min_hours          REAL NOT NULL DEFAULT 1 CHECK (min_hours > 0),
    band_percent       INTEGER NOT NULL DEFAULT 25 CHECK (band_percent BETWEEN 0 AND 100),
    note               TEXT,
    updated_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 10. Settlements
CREATE TABLE IF NOT EXISTS settlements (
    id                SERIAL PRIMARY KEY,
    booking_id        INTEGER NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,
    worker_id         INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    hours_worked      REAL NOT NULL CHECK (hours_worked > 0),
    materials_paise   INTEGER NOT NULL DEFAULT 0 CHECK (materials_paise >= 0),
    work_note         TEXT,
    standard_paise    INTEGER NOT NULL CHECK (standard_paise >= 0),
    proposed_paise    INTEGER NOT NULL CHECK (proposed_paise > 0),
    counter_paise     INTEGER CHECK (counter_paise IS NULL OR counter_paise > 0),
    customer_note     TEXT,
    agreed_paise      INTEGER CHECK (agreed_paise IS NULL OR agreed_paise > 0),
    status            VARCHAR(20) NOT NULL DEFAULT 'proposed'
                      CHECK (status IN ('proposed', 'countered', 'agreed', 'disputed')),
    paid_via          VARCHAR(20) CHECK (paid_via IS NULL OR paid_via IN ('cash', 'upi', 'other')),
    dispute_id        INTEGER REFERENCES disputes(id) ON DELETE SET NULL,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at      TIMESTAMP WITH TIME ZONE,
    agreed_at         TIMESTAMP WITH TIME ZONE
);

-- 11. Schema Migrations Tracker
CREATE TABLE IF NOT EXISTS schema_migrations (
    version         INTEGER PRIMARY KEY,
    applied_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 12. Performance Indexes
CREATE INDEX IF NOT EXISTS idx_workers_trade        ON workers (trade);
CREATE INDEX IF NOT EXISTS idx_sessions_user        ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_disputes_status      ON disputes (status);
CREATE INDEX IF NOT EXISTS idx_bookings_status      ON bookings (status);
CREATE INDEX IF NOT EXISTS idx_bookings_trade       ON bookings (trade);
CREATE INDEX IF NOT EXISTS idx_bookings_customer    ON bookings (customer_user_id);
CREATE INDEX IF NOT EXISTS idx_assignments_booking  ON assignments (booking_id);
CREATE INDEX IF NOT EXISTS idx_assignments_worker   ON assignments (worker_id);
CREATE INDEX IF NOT EXISTS idx_declines_booking     ON declines (booking_id);
CREATE INDEX IF NOT EXISTS idx_declines_worker      ON declines (worker_id);
