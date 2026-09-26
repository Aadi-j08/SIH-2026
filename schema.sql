-- =============================================================================
-- SahakarSetu — PostgreSQL Schema (Neon.tech / Supabase / Render)
-- 100% Free Production Database Schema
-- =============================================================================

-- 1. Cooperative Federation (one row per member cooperative; id=1 is the original)
CREATE TABLE IF NOT EXISTS cooperative_federations (
    id                INTEGER PRIMARY KEY,
    name              VARCHAR(255) NOT NULL,
    code              VARCHAR(60) NOT NULL UNIQUE,
    region            VARCHAR(100),
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
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO cooperative_federations (id, code, name, short_name, registration_id, established, area, radius_km,
    verified, worker_kyc, payments_verified, secretary, coordinator, last_meeting, weekly_job_limit, fund_allocation)
VALUES (1, 'SABHA-2026', 'Bhopal Urban Services Cooperative', 'Bhopal Central Cooperative', 'SABHA-MP-0417',
    2026, 'Bhopal', 12, 1, 1, 1, NULL, NULL, '2026-09-04', 6, '{}')
ON CONFLICT (id) DO NOTHING;

-- 2. Workers
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
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 9. Users (Authentication)
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
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_portal_phone UNIQUE (portal, phone)
);

-- 8. Sessions
CREATE TABLE IF NOT EXISTS sessions (
    token_hash      VARCHAR(255) PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL
);

-- 10. Bookings
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
                    CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed', 'cancelled')),
    urgency_level   VARCHAR(20) NOT NULL DEFAULT 'medium'
                    CHECK (urgency_level IN ('low', 'medium', 'high', 'urgent')),
    customer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. Assignments
CREATE TABLE IF NOT EXISTS assignments (
    id              SERIAL PRIMARY KEY,
    booking_id      INTEGER NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,
    worker_id       INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    score           REAL,
    accepted_at     TIMESTAMP WITH TIME ZONE,
    started_at      TIMESTAMP WITH TIME ZONE,
    start_selfie_url TEXT,
    end_photo_url   TEXT,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 12. Declines
CREATE TABLE IF NOT EXISTS declines (
    id              SERIAL PRIMARY KEY,
    booking_id      INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    worker_id       INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    reason          VARCHAR(50) NOT NULL CHECK (reason IN ('unwell', 'too_far', 'already_booked', 'not_my_job', 'other')),
    note            TEXT,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 13. Cooperative Info (legacy singleton kept as a convenience view over the federation)
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

-- 14. Disputes
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
    cooperative_id    INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at       TIMESTAMP WITH TIME ZONE
);

-- 15. Standard Rate Card
CREATE TABLE IF NOT EXISTS standard_rates (
    trade              VARCHAR(100) NOT NULL,
    cooperative_id     INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    visit_charge_paise INTEGER NOT NULL CHECK (visit_charge_paise >= 0),
    hourly_rate_paise  INTEGER NOT NULL CHECK (hourly_rate_paise > 0),
    min_hours          REAL NOT NULL DEFAULT 1 CHECK (min_hours > 0),
    band_percent       INTEGER NOT NULL DEFAULT 25 CHECK (band_percent BETWEEN 0 AND 100),
    note               TEXT,
    updated_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade, cooperative_id)
);

-- 16. Settlements
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
    cooperative_id    INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
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

-- 19. User Feedback (for continuous improvement from real users)
CREATE TABLE IF NOT EXISTS feedback (
    id              SERIAL PRIMARY KEY,
    type            VARCHAR(20) NOT NULL CHECK (type IN ('bug', 'feature', 'general')),
    rating          INTEGER CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    message         TEXT NOT NULL,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    user_name       VARCHAR(255),
    user_phone      VARCHAR(20),
    user_portal     VARCHAR(20) CHECK (user_portal IN ('ghar', 'kaam', 'sabha')),
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    resolved        INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_type      ON feedback (type);
CREATE INDEX IF NOT EXISTS idx_feedback_user      ON feedback (user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_resolved  ON feedback (resolved);
CREATE INDEX IF NOT EXISTS idx_feedback_coop      ON feedback (cooperative_id);

-- 20. Tenant-aware performance indexes
CREATE INDEX IF NOT EXISTS idx_workers_cooperative     ON workers (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_bookings_cooperative    ON bookings (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_assignments_cooperative  ON assignments (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_disputes_cooperative     ON disputes (cooperative_id);

-- 21. Worker profile (skills, certifications, portfolio, documents)
CREATE TABLE IF NOT EXISTS worker_skills (
    id              SERIAL PRIMARY KEY,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    skill           VARCHAR(100) NOT NULL,
    level           VARCHAR(20) NOT NULL DEFAULT 'intermediate' CHECK (level IN ('beginner', 'intermediate', 'expert')),
    verified        INTEGER NOT NULL DEFAULT 0,
    verified_by     INTEGER REFERENCES users(id),
    verified_at     TIMESTAMP WITH TIME ZONE,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (worker_id, skill)
);

CREATE TABLE IF NOT EXISTS certifications (
    id              SERIAL PRIMARY KEY,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    name            VARCHAR(120) NOT NULL,
    issuing_org     VARCHAR(120),
    issue_date      DATE,
    expiry_date     DATE,
    document        TEXT,                            -- off-FS file path / URL
    verified        INTEGER NOT NULL DEFAULT 0,
    verified_by     INTEGER REFERENCES users(id),
    verified_at     TIMESTAMP WITH TIME ZONE,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (worker_id, name, issuing_org, issue_date)
);

CREATE TABLE IF NOT EXISTS portfolio_items (
    id              SERIAL PRIMARY KEY,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    image_url       TEXT NOT NULL,                   -- off-FS storage reference
    caption         TEXT,
    category        VARCHAR(30) CHECK (category IN ('before', 'after', 'work_in_progress', 'other')),
    verified        INTEGER NOT NULL DEFAULT 0,
    verified_by     INTEGER REFERENCES users(id),
    verified_at     TIMESTAMP WITH TIME ZONE,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS worker_documents (
    id              SERIAL PRIMARY KEY,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    document_type   VARCHAR(30) NOT NULL,            -- id_proof, insurance, vehicle, other
    file_url        TEXT NOT NULL,                   -- off-FS storage reference
    uploaded_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    UNIQUE (worker_id, document_type, file_url)
);

CREATE INDEX IF NOT EXISTS idx_worker_skills_worker    ON worker_skills (worker_id);
CREATE INDEX IF NOT EXISTS idx_worker_skills_coop      ON worker_skills (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_certifications_worker   ON certifications (worker_id);
CREATE INDEX IF NOT EXISTS idx_certifications_coop     ON certifications (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_certifications_verified ON certifications (verified);
CREATE INDEX IF NOT EXISTS idx_portfolio_worker        ON portfolio_items (worker_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_coop          ON portfolio_items (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_worker_documents_worker  ON worker_documents (worker_id);
CREATE INDEX IF NOT EXISTS idx_worker_documents_coop    ON worker_documents (cooperative_id);

-- 22. Worker benefits (pension/medical/disability)
CREATE TABLE IF NOT EXISTS benefits (
    id              SERIAL PRIMARY KEY,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    kind            VARCHAR(20) NOT NULL CHECK (kind IN ('pension', 'medical', 'disability', 'other')),
    name            VARCHAR(120) NOT NULL,
    description     TEXT,
    eligible        INTEGER NOT NULL DEFAULT 0,
    claimed         INTEGER NOT NULL DEFAULT 0,
    amount_rupees   REAL CHECK (amount_rupees IS NULL OR amount_rupees >= 0),
    start_date      TEXT,
    end_date        TEXT,
    document        TEXT,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_benefits_worker ON benefits (worker_id);
CREATE INDEX IF NOT EXISTS idx_benefits_coop   ON benefits (cooperative_id);

-- 23. Insurance policies held by the cooperative
CREATE TABLE IF NOT EXISTS insurance_policies (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    kind            VARCHAR(20) NOT NULL CHECK (kind IN ('health', 'accident', 'life', 'liability', 'other')),
    insurer         VARCHAR(120),
    policy_number   VARCHAR(120),
    premium_rupees  REAL NOT NULL CHECK (premium_rupees >= 0),
    premium_paid    INTEGER NOT NULL DEFAULT 0,
    coverage_paise  INTEGER NOT NULL CHECK (coverage_paise >= 0),
    start_date      TEXT,
    end_date        TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_insurance_coop   ON insurance_policies (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_insurance_active ON insurance_policies (active);

-- 24. Worker grievances
CREATE TABLE IF NOT EXISTS grievances (
    id              SERIAL PRIMARY KEY,
    worker_id       INTEGER REFERENCES workers(id),
    raised_by_user_id INTEGER REFERENCES users(id),
    kind            VARCHAR(20) NOT NULL CHECK (kind IN ('wage', 'safety', 'equipment', 'assignment', 'other')),
    title           VARCHAR(140) NOT NULL,
    description     TEXT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'triaged', 'in_progress', 'resolved', 'rejected')),
    resolution      TEXT,
    priority        VARCHAR(10) NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_grievances_worker ON grievances (worker_id);
CREATE INDEX IF NOT EXISTS idx_grievances_status  ON grievances (status);
CREATE INDEX IF NOT EXISTS idx_grievances_coop    ON grievances (cooperative_id);
