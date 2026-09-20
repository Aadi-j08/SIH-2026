# 🏛️ SahakarSetu (सहकारसेतु)
### *AI-Powered Civic Cooperative Platform for Fair Work Allocation & Community Governance*
**Smart India Hackathon (SIH 2026)**

[![Backend Tests](https://img.shields.io/badge/Pytest-220%20Passed%20(100%25)-brightgreen.svg?style=flat-square)](tests/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%200.115-blue.svg?style=flat-square)](https://fastapi.tiangolo.com)
[![AI/ML](https://img.shields.io/badge/AI%2FML-Gemini%201.5%20Flash%20%2B%20scikit--learn-orange.svg?style=flat-square)](app/services/)
[![Database](https://img.shields.io/badge/Database-Cloud%20PostgreSQL%20%2B%20SQLite-indigo.svg?style=flat-square)](schema.sql)
[![Hosting](https://img.shields.io/badge/Hosting-100%25%20Free%20Tier%20(₹0)-green.svg?style=flat-square)](render.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

---

## 📌 Problem & Vision
Urban household service aggregators (commercial gig apps) exploit informal artisans through 20-30% commissions, arbitrary algorithm penalties, and opaque ratings that monopolize work among top earners.

**SahakarSetu** decentralizes municipal household services by empowering local artisan cooperatives:
* ⚖️ **Fair Work Distribution:** Bipartite matching algorithm ensures idle artisans get equitable opportunities rather than work being monopolized by a few.
* 🎙️ **Multilingual Voice AI:** Google Gemini 1.5 Flash understands spoken Hindi, Hinglish, and regional queries with zero-setup offline fallback.
* 📈 **Machine Learning Demand Forecasting:** `scikit-learn` Ridge regression predicts weekly ward demand and guarantees minimum wage floors without predatory surge pricing.
* 🤝 **AI Dispute Mediation:** Transparent midpoint settlement calculator & diplomatic bilingual council mediation notes.
* 💰 **Zero Platform Fees:** 100% direct customer-to-worker payment; transparent community fund ledger allocation (85% artisan · 10% welfare · 5% ops).

---

## 🏛️ The Three Portals

| Portal | Audience | Core Capabilities |
|---|---|---|
| **🏡 Ghar** | Households & Citizens | Voice & text booking, live job tracking, transparent standard rate quotes, fair price agreement, and review rating. |
| **🔧 Kaam** | Skilled Artisans & Workers | Voice availability declaration, job accept/decline, bill proposal against rate card, direct cash/UPI receipt. |
| **🏛️ Sabha** | Cooperative Council & Ward Leaders | Global batch dispatch, ML demand heatmaps, dispute resolution centre, cooperative welfare fund ledger, worker KYC. |

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Client Layer [Frontend Client - React 18 / Vite / PWA]
        GHAR[🏡 Ghar Portal - Citizens]
        KAAM[🔧 Kaam Portal - Workers]
        SABHA[🏛️ Sabha Portal - Council]
    end

    subgraph CDN [Edge CDN - 100% Free]
        CF[Cloudflare Pages / Vercel]
    end

    subgraph Backend Layer [FastAPI Web Service - Render.com Free Tier]
        API[FastAPI Gateway & Auth]
        
        subgraph AIML [AI / ML & Analytics Services]
            GEMINI[🤖 Gemini 1.5 Flash Multilingual NLP]
            SKLEARN[📈 Scikit-Learn Demand Forecaster]
            ALLOC[⚖️ Fair Bipartite Matching Engine]
            DISPUTE[🤝 AI Dispute Advisor & Sentiment]
        end
    end

    subgraph Data Layer [Database Layer]
        PG[(Cloud PostgreSQL - Neon.tech / Supabase)]
        SQLITE[(SQLite + WAL Mode - Local Fallback)]
    end

    Client Layer --> CF
    CF --> API
    API --> AIML
    API --> PG
    API -. Local Dev / Pytest .-> SQLITE
```

---

## 🤖 AI / ML Architecture Breakdown

### 1. Multilingual Voice NLP Engine (`gemini_nlp.py`)
* Processes conversational voice queries in **Hindi (Devanagari)**, **Hinglish**, and **English**.
* Enforces strict JSON extraction: `{ trade, urgency, preferred_time, notes }`.
* **Offline Resilience:** Embedded keyword & regex heuristic fallback guarantees 100% uptime if internet or API limits expire during demonstrations.

### 2. Tabular Demand & Fair-Wage Forecaster (`demand_forecast.py`)
* Regularized `Ridge` regression trained on day-of-week, weekend trends, and seasonal lag patterns.
* Calculates guaranteed **Wage Floor Band** + **Fair Recommended Rate** preventing price gouging.

### 3. Fair Batch Worker Dispatch Engine (`worker_allocation.py`)
* Computes normalized multi-objective utility scores:
  $$\text{Utility} = 0.35 \times \text{Proximity} + 0.35 \times \text{Fairness (Idle Rotation)} + 0.20 \times \text{Rating} + 0.10 \times \text{Status}$$
* Solves global maximum-weight bipartite matching across multiple open bookings.

### 4. AI Dispute Resolution Advisor (`dispute_advisor.py`)
* Computes mathematical material-cost-safe midpoint settlements.
* Generates diplomatic bilingual (Hindi/English) mediation notes for cooperative council sign-off.
* Analyzes review sentiment (`TextBlob` + Lexicon) to proactively flag toxic grievances.

---

## ⚡ Quick Start (Local Setup)

### 1. Backend Setup
```bash
# Clone repository
git clone https://github.com/Aadi-j08/SIH-2026.git
cd SIH-2026

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Seed realistic demo data
python3 scripts/seed_demo_data.py

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup (In a separate terminal)
```bash
cd frontend
npm install
npm run dev
```

| Interface | Local URL | Description |
|---|---|---|
| **Web Application** | `http://localhost:5173/` | React PWA (Landing + Portals) |
| **Interactive API Docs** | `http://localhost:8000/docs` | Swagger / OpenAPI UI |
| **API Health Check** | `http://localhost:8000/` | Backend status & engine metadata |

---

## 🔑 Demo User Accounts (Pre-Seeded)

All demo accounts share the password: **`demo1234`**

| Portal | Role | Phone Number | Identity / Locality |
|---|---|---|---|
| **🏡 Ghar** | Customer | `9876543210` | Aarav Sharma (Resident, Arera Colony) |
| **🔧 Kaam** | Artisan / Worker | `9876543211` | Rameshwar Prasad (Verified Plumber, 4.8★) |
| **🏛️ Sabha** | Council Secretary | `9876543212` | Sunita Verma (Cooperative Secretary) |

*Council Sign-up Code for new registrations:* `SABHA-2026`

---

## 🧪 Test Suite & Quality Assurance

Our codebase contains comprehensive automated test coverage across authentication, AI services, pricing formulas, and database integrity:

```bash
# Run all 220 tests
pytest -v

# Run frontend typecheck & build
cd frontend && npm run build
```

```
============================== test session starts ===============================
collected 220 items                                                            
tests/test_allocation.py ............                                    [  5%]
tests/test_api.py ................                                       [ 12%]
tests/test_assistant.py ..............                                   [ 19%]
tests/test_auth.py ..........                                            [ 23%]
tests/test_authz.py ...............                                      [ 30%]
tests/test_booking_flow.py .............................                 [ 43%]
tests/test_constraints.py ...............                                [ 50%]
tests/test_database_engine.py ..                                         [ 51%]
tests/test_demand_forecast_ml.py ...                                     [ 52%]
tests/test_dispute_advisor.py ....                                       [ 54%]
tests/test_forecast.py .......                                           [ 57%]
tests/test_gemini_nlp.py .....                                           [ 60%]
tests/test_kaam.py ................                                      [ 67%]
tests/test_language.py ...                                               [ 68%]
tests/test_pricing.py ..........                                         [ 73%]
tests/test_sabha.py ..........                                           [ 77%]
tests/test_staffing.py .......                                           [ 80%]
tests/test_trades.py .....................                               [ 90%]
tests/test_voice.py ...................                                  [ 99%]
tests/test_worker_allocation.py ..                                       [100%]
======================= 220 passed, 2 warnings in 13.38s =======================
```

---

## ☁️ 100% Free Production Deployment

| Component | Platform | Configuration | Cost |
|---|---|---|---|
| **Frontend** | **Cloudflare Pages / Vercel** | SPA Build (`npm run build`) with Global CDN & SSL | **₹0** |
| **Backend** | **Render.com** | Python Web Service via [`render.yaml`](render.yaml) | **₹0** |
| **Database** | **Neon.tech / Supabase** | Serverless PostgreSQL via [`schema.sql`](schema.sql) | **₹0** |
| **AI / NLP** | **Google AI Studio** | Gemini 1.5 Flash Free Tier API | **₹0** |

---

## 👥 Team
* **AI/ML & Backend Lead:** Aman Yadav,Aadi Jain,Abhishek Meena
* **Project Repository:** [SIH-2026](https://github.com/Aadi-j08/SIH-2026)
* **Submission Event:** Smart India Hackathon 2026
