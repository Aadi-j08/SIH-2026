# 🎤 SahakarSetu — Project Presentation & Explanation Guide

> **Target Audience**: SIH Evaluators, Hackathon Judges, Mentors, and Teammates.  
> **Use this guide to**: Explain the entire project, its architecture, algorithms, and business model in **under 3 minutes** or during a deep-dive technical interview.

---

## ⚡ 1. The 30-Second Elevator Pitch

> *"Commercial aggregators like Urban Company exploit blue-collar artisans with 20-30% commissions, arbitrary algorithm penalties, and opaque ratings that monopolize work among top earners.*  
> 
> ***SahakarSetu (सहकारसेतु)*** *is a decentralized, municipal cooperative platform that provides 0% commission direct work matching.*  
> 
> *It features an **Urgency-Weighted Bipartite Dispatch Engine** that balances proximity with fair income distribution, a **Multilingual Voice AI** powered by Google Gemini for non-tech-savvy artisans, an **ML Demand Forecaster** that sets minimum wage floors without predatory surge pricing, and an **85/10/5 Transparent Cooperative Ledger** with dynamic UPI split payments."*

---

## 🏛️ 2. The Tri-Portal Ecosystem (Who uses what?)

```
+-----------------------------------------------------------------------------------+
|                                SAHAKARSETU ECOSYSTEM                              |
+-------------------------+-------------------------------+-------------------------+
|     🏡 GHAR PORTAL      |        🔧 KAAM PORTAL         |     🏛️ SABHA PORTAL      |
|  (Citizens / Customers) |      (Skilled Artisans)       |  (Cooperative Council)  |
+-------------------------+-------------------------------+-------------------------+
| • Voice/Text Booking    | • Voice Schedule Declaration  | • Algorithmic Dispatch  |
| • Urgency Mode Selector | • 1-Tap Accept / Decline      | • ML Demand Forecasting |
| • Live Radar Tracking   | • Proof-of-Work Selfies       | • Staffing Surge Alerts |
| • Transparent UPI Pay   | • Rate Card Bill Generation   | • AI Dispute Mediation  |
| • Dispute Reporting     | • 85% Direct UPI Payout       | • Welfare Fund Ledger   |
+-------------------------+-------------------------------+-------------------------+
```

---

## 🧠 3. Core Algorithms Explained in Simple Terms

### 1️⃣ Urgency-Weighted Bipartite Allocation (`app/services/worker_allocation.py`)
* **The Problem**: Uber/Urban Company algorithms always give jobs to the nearest 5-star worker, starving new or less active workers.
* **Our Solution**:
  * **Standard Jobs**: Balances Proximity ($40\%$), Fairness/Idle-Rotation ($35\%$), and Customer Rating ($25\%$).
  * **Emergency Jobs (तत्काल)**: Automatically shifts weights to prioritize speed ($70\%$ Proximity, $20\%$ Rating, $10\%$ Fairness) for critical repairs like pipe bursts or short circuits.

### 2️⃣ Multilingual Voice AI Parser (`app/services/voice.py` & `gemini_nlp.py`)
* **The Problem**: Indian artisans cannot easily type schedules into complex English web forms.
* **Our Solution**: Artisans simply speak in Hindi/Hinglish (*"Kal subah 9 baje se 1 baje tak free hoon"*).
  * Fast token regex extracts time slots locally.
  * Google Gemini 1.5 Flash handles complex colloquial expressions with 100% offline fallback resilience.

### 3️⃣ Demand & Minimum-Wage Forecaster (`app/services/demand_forecast.py`)
* **The Problem**: Private aggregators use predatory surge pricing that hurts citizens while underpaying workers.
* **Our Solution**: `scikit-learn` Ridge regression analyzes 30-day booking volume by day-of-week and ward to forecast weekly demand and establish guaranteed minimum wage floors for workers.

### 4️⃣ Transparent 85 / 10 / 5 Cooperative Split (`app/services/ledger.py`)
* Every ₹100 paid by the citizen through the dynamic UPI QR is transparently split:
  * 👷 **₹85** $\to$ Direct to Worker's UPI / Bank Account
  * 🛡️ **₹10** $\to$ Cooperative Emergency Welfare & Tool Insurance Fund
  * ⚙️ **₹5** $\to$ Platform Operations & SMS Gateway (0% private company profit)

### 5️⃣ AI Payment Discrepancy & Dispute Advisor (`app/services/dispute_advisor.py`)
* Automatically detects off-platform cash bypass or overcharging.
* Calculates fair mathematical compromise between worker ask and customer counter-offer while protecting material costs.

---

## 📁 4. Project Directory Map (How to navigate the code)

```
SIH-2026/
├── app/                            # 🚀 BACKEND (FastAPI)
│   ├── database.py                 # DB connection (PostgreSQL + SQLite) & zero-downtime migrations
│   ├── auth.py                     # PBKDF2 hashing, sessions & Role-Based Access Control
│   ├── main.py                     # FastAPI entrypoint, lifespan & root routes
│   ├── services/                   # 🧠 ALL ALGORITHMS & AI
│   │   ├── worker_allocation.py    # Urgency-weighted bipartite dispatch engine
│   │   ├── voice.py & gemini_nlp.py# Multilingual voice parsing & intent extraction
│   │   ├── demand_forecast.py      # Statistical/ML demand forecasting
│   │   ├── ledger.py               # 85/10/5 transparent split & UPI QR generator
│   │   └── dispute_advisor.py      # AI dispute resolution & sentiment analysis
│   └── routers/                    # 🌐 REST API ENDPOINTS
│       ├── auth.py, booking_flow.py, kaam.py, pricing.py, sabha.py, assistant.py
├── frontend/                       # 🎨 FRONTEND (React 18 + TypeScript + Vite)
│   └── src/
│       ├── pages/                  # Customer.tsx, Worker.tsx, WorkerJobs.tsx, sabha/*.tsx
│       ├── components/             # LiveBookingTracker.tsx, VoiceAvailability.tsx, Settlement.tsx
│       ├── api.ts                  # Typed TypeScript API client SDK
│       └── styles.css              # Custom glassmorphic responsive design system
├── tests/                          # 🧪 AUTOMATED TESTS (224/224 tests passing)
└── docs/                           # 📖 SPECIFICATIONS & DEPLOYMENT GUIDES
```

---

## 🎯 5. Quick 2-Minute Live Demo Flow

1. **Step 1 (Citizen Booking)**:
   * Open **Ghar Portal** (`/app/customer`).
   * Choose trade (e.g. *Plumbing*), select **🚨 Urgent Mode**, and click *"Book Service"*.
2. **Step 2 (Artisan 1-Tap Accept & Verification)**:
   * Open **Kaam Portal** (`/app/worker/jobs`).
   * Worker receives urgent job alert, taps **Accept**, and uploads **Start Selfie Proof-of-Work**.
   * Booking status transitions to `In Progress` on citizen's live radar tracker.
3. **Step 3 (Bill & Transparent UPI QR)**:
   * Worker taps **Complete Work**, inputs materials & labor cost.
   * Customer sees verified completion photo, 85/10/5 breakdown, and dynamic NPCI UPI QR code.
4. **Step 4 (Sabha Council Governance)**:
   * Open **Sabha Portal** (`/app/sabha`).
   * View ML demand forecast heatmap, cooperative welfare fund balance, and AI dispute recommendations.

---

## ❓ 6. Top 5 Questions Evaluators Will Ask (And How to Answer)

| Question | Winning Answer |
| :--- | :--- |
| **"How is this different from Urban Company?"** | Urban Company takes 25%+ commissions, punishes workers algorithmically, and uses surge pricing. SahakarSetu is cooperative-owned, takes 0% private commission, guarantees fair rotation across all workers, and channels 10% into member welfare. |
| **"What if two workers accept a job at the same time?"** | Our backend utilizes database-level atomic transactions and optimistic locking in `app/kaam.py`. The first worker to confirm wins the assignment; the second worker is immediately notified and returned to the top of the queue for the next matching job. |
| **"How do you handle worker fraud or off-platform cash bypass?"** | 1. **Proof-of-Work**: Workers must submit geotagged selfies at job start and completion photos at finish.<br>2. **Payment Discrepancy Advisor**: `analyze_payment_discrepancy` audits customer-reported payment against worker invoices and flags anomalies to the council. |
| **"What if an artisan speaks in Hindi or cannot type?"** | Our voice engine uses Web Audio API to capture speech, processes Hindi/Hinglish directly with Google Gemini 1.5 Flash, and extracts structured time slots with 100% offline regex fallback. |
| **"What is the hosting cost?"** | Exactly **₹0**. The architecture runs entirely on free-tier services (Render/Fly.io for FastAPI, Neon.tech for PostgreSQL, Cloudflare Pages for React PWA, Gemini free tier). |
