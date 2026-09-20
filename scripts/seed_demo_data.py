"""
Universal Demo Data Seeder for SahakarSetu.

Auto-detects active database engine:
- If DATABASE_URL is set -> Seeds Cloud PostgreSQL (Neon.tech / Supabase)
- Else                   -> Seeds Local SQLite (sahakarsetu.db)

Populates:
1. Cooperative Profile (Bhopal Shramik Sahakari Samiti)
2. Standard Rate Cards for all trades
3. 8 Active Verified Workers in Bhopal localities
4. Demo Accounts (Password: demo1234):
   - Ghar (Customer): 9876543210
   - Kaam (Worker):   9876543211
   - Sabha (Council):  9876543212
5. 4 Sample Bookings & 1 Active Dispute for AI Advisor demo

Usage:
    python3 scripts/seed_demo_data.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

from app.auth import hash_password

load_dotenv()


def seed_postgres(db_url: str):
    import psycopg

    print("🔌 Connecting to Cloud PostgreSQL (Neon.tech)...")
    demo_pass_hash = hash_password("demo1234")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                TRUNCATE TABLE declines, assignments, settlements, disputes, bookings, sessions, users, workers, cooperative, standard_rates RESTART IDENTITY CASCADE;
            """)

            cur.execute("""
                INSERT INTO cooperative (
                    id, name, short_name, registration_id, established, area, radius_km,
                    verified, worker_kyc, payments_verified, secretary, coordinator,
                    last_meeting, weekly_job_limit, fund_allocation
                ) VALUES (
                    1, 'Bhopal Shramik Sahakari Samiti', 'Bhopal Sabha', 'MP/BPL/COOP/2026/042',
                    2021, 'Bhopal Municipal Corporation Area', 25.0, 1, 1, 1,
                    'Sunita Verma', 'Aman Yadav', '2026-09-15', 6,
                    '{"welfare": 40, "emergency_fund": 30, "training": 20, "ops": 10}'
                );
            """)

            rates = [
                ("plumbing", 10000, 35000, 1.0, 20, "Cooperative standard rate for residential plumbing repairs"),
                ("electrician", 12000, 40000, 1.0, 20, "Wiring, switchboard, inverter, and appliance repair"),
                ("carpentry", 15000, 45000, 2.0, 25, "Furniture repair, door fitting, and woodwork"),
                ("painting", 20000, 50000, 4.0, 25, "Interior and exterior wall painting with primer"),
                ("masonry", 20000, 55000, 4.0, 20, "Civil repairs, tiling, brickwork, and plastering"),
                ("appliance", 15000, 45000, 1.0, 20, "Air cooler, motor, pump, and washing machine service"),
            ]
            for trade, visit, hourly, min_h, band, note in rates:
                cur.execute("""
                    INSERT INTO standard_rates (trade, visit_charge_paise, hourly_rate_paise, min_hours, band_percent, note)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (trade, visit, hourly, min_h, band, note))

            workers_data = [
                ("Rameshwar Prasad", "9876543211", "plumbing", 23.2332, 77.4343, 2, 4.8, "active"),
                ("Vikram Singh", "9876543222", "plumbing", 23.2201, 77.4120, 0, 4.6, "active"),
                ("Deepak Malviya", "9876543233", "electrician", 23.2450, 77.4010, 1, 4.9, "active"),
                ("Karan Johari", "9876543244", "electrician", 23.1980, 77.4420, 4, 4.5, "active"),
                ("Mohammad Arif", "9876543255", "carpentry", 23.2510, 77.4600, 1, 4.7, "active"),
                ("Suresh Kushwaha", "9876543266", "masonry", 23.2620, 77.4100, 0, 4.4, "active"),
                ("Santosh Chouhan", "9876543277", "painting", 23.2100, 77.4500, 3, 4.8, "active"),
                ("Mukesh Soni", "9876543288", "appliance", 23.2400, 77.4200, 1, 4.6, "active"),
            ]

            worker_ids = {}
            for name, phone, trade, lat, lon, jobs, rating, status in workers_data:
                cur.execute("""
                    INSERT INTO workers (name, phone, trade, latitude, longitude, jobs_this_week, rating, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                """, (name, phone, trade, lat, lon, jobs, rating, status))
                worker_ids[phone] = cur.fetchone()[0]

            users = [
                ("ghar", "9876543210", "Aarav Sharma (Customer)", "Arera Colony", None, None),
                ("kaam", "9876543211", "Rameshwar Prasad (Worker)", "Arera Colony", None, worker_ids["9876543211"]),
                ("sabha", "9876543212", "Sunita Verma (Secretary)", "Bhopal Central", "secretary", None),
            ]
            for portal, phone, name, locality, role, wid in users:
                cur.execute("""
                    INSERT INTO users (portal, phone, name, password_hash, locality, role, worker_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (portal, phone, name, demo_pass_hash, locality, role, wid))

            cur.execute("""
                INSERT INTO bookings (customer_name, customer_phone, trade, latitude, longitude, address, status)
                VALUES 
                ('Pooja Patel', '9811111111', 'plumbing', 23.2300, 77.4300, 'E-3/42 Arera Colony, Bhopal', 'pending'),
                ('Rajesh Gupta', '9822222222', 'plumbing', 23.2250, 77.4200, 'Zone-1, MP Nagar, Bhopal', 'pending'),
                ('Anjali Saxena', '9833333333', 'electrician', 23.2400, 77.4050, 'B-Sector, Shahpura, Bhopal', 'pending'),
                ('Sunil Mehta', '9844444444', 'carpentry', 23.2500, 77.4550, 'Sector-A, Indrapuri, Bhopal', 'completed');
            """)

            cur.execute("""
                INSERT INTO bookings (customer_name, customer_phone, trade, latitude, longitude, address, status)
                VALUES ('Manish Jain', '9855555555', 'plumbing', 23.2310, 77.4320, '12 Arera Colony, Bhopal', 'completed')
                RETURNING id;
            """)
            dispute_bid = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO settlements (
                    booking_id, worker_id, hours_worked, materials_paise, work_note,
                    standard_paise, proposed_paise, counter_paise, customer_note, status
                ) VALUES (%s, %s, 2.0, 15000, 'Replaced kitchen main valve and PVC connector pipe',
                          70000, 85000, 75000, 'Work was fine but expected standard rate', 'disputed');
            """, (dispute_bid, worker_ids["9876543211"]))

            cur.execute("""
                INSERT INTO disputes (
                    booking_id, kind, raised_by, amount_paise, description, status
                ) VALUES (
                    %s, 'payment', 'worker', 10000,
                    'Customer refuses to reimburse 150 for heavy duty PVC connector valve bought from hardware store',
                    'open'
                );
            """, (dispute_bid,))

            conn.commit()
    print("✅ Successfully seeded Cloud PostgreSQL (Neon.tech)!")


def seed_sqlite():
    from app.database import connection, init_db

    print("📁 Connecting to Local SQLite (sahakarsetu.db)...")
    init_db()
    demo_pass_hash = hash_password("demo1234")

    with connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO cooperative (
            id, name, short_name, registration_id, established, area, radius_km,
            verified, worker_kyc, payments_verified, secretary, coordinator,
            last_meeting, weekly_job_limit, fund_allocation
        ) VALUES (
            1, 'Bhopal Shramik Sahakari Samiti', 'Bhopal Sabha', 'MP/BPL/COOP/2026/042',
            2021, 'Bhopal Municipal Corporation Area', 25.0, 1, 1, 1,
            'Sunita Verma', 'Aman Yadav', '2026-09-15', 6,
            '{"welfare": 40, "emergency_fund": 30, "training": 20, "ops": 10}'
        )
        """)

        rates = [
            ("plumbing", 10000, 35000, 1.0, 20, "Cooperative standard rate for residential plumbing repairs"),
            ("electrician", 12000, 40000, 1.0, 20, "Wiring, switchboard, inverter, and appliance repair"),
            ("carpentry", 15000, 45000, 2.0, 25, "Furniture repair, door fitting, and woodwork"),
            ("painting", 20000, 50000, 4.0, 25, "Interior and exterior wall painting with primer"),
            ("masonry", 20000, 55000, 4.0, 20, "Civil repairs, tiling, brickwork, and plastering"),
            ("appliance", 15000, 45000, 1.0, 20, "Air cooler, motor, pump, and washing machine service"),
        ]
        for trade, visit, hourly, min_h, band, note in rates:
            conn.execute("""
            INSERT OR REPLACE INTO standard_rates (trade, visit_charge_paise, hourly_rate_paise, min_hours, band_percent, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (trade, visit, hourly, min_h, band, note))

        workers_data = [
            ("Rameshwar Prasad", "9876543211", "plumbing", 23.2332, 77.4343, 2, 4.8),
            ("Vikram Singh", "9876543222", "plumbing", 23.2201, 77.4120, 0, 4.6),
            ("Deepak Malviya", "9876543233", "electrician", 23.2450, 77.4010, 1, 4.9),
            ("Karan Johari", "9876543244", "electrician", 23.1980, 77.4420, 4, 4.5),
            ("Mohammad Arif", "9876543255", "carpentry", 23.2510, 77.4600, 1, 4.7),
            ("Suresh Kushwaha", "9876543266", "masonry", 23.2620, 77.4100, 0, 4.4),
            ("Santosh Chouhan", "9876543277", "painting", 23.2100, 77.4500, 3, 4.8),
            ("Mukesh Soni", "9876543288", "appliance", 23.2400, 77.4200, 1, 4.6),
        ]

        worker_ids = {}
        for name, phone, trade, lat, lon, jobs, rating in workers_data:
            cur = conn.execute("""
            INSERT INTO workers (name, phone, trade, latitude, longitude, jobs_this_week, rating, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """, (name, phone, trade, lat, lon, jobs, rating))
            worker_ids[phone] = cur.lastrowid

        users = [
            ("ghar", "9876543210", "Aarav Sharma (Customer)", "Arera Colony", None, None),
            ("kaam", "9876543211", "Rameshwar Prasad (Worker)", "Arera Colony", None, worker_ids["9876543211"]),
            ("sabha", "9876543212", "Sunita Verma (Secretary)", "Bhopal Central", "secretary", None),
        ]
        for portal, phone, name, locality, role, wid in users:
            conn.execute("""
            INSERT OR REPLACE INTO users (portal, phone, name, password_hash, locality, role, worker_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (portal, phone, name, demo_pass_hash, locality, role, wid))

        conn.execute("""
        INSERT INTO bookings (customer_name, customer_phone, trade, latitude, longitude, address, status)
        VALUES 
        ('Pooja Patel', '9811111111', 'plumbing', 23.2300, 77.4300, 'E-3/42 Arera Colony, Bhopal', 'pending'),
        ('Rajesh Gupta', '9822222222', 'plumbing', 23.2250, 77.4200, 'Zone-1, MP Nagar, Bhopal', 'pending'),
        ('Anjali Saxena', '9833333333', 'electrician', 23.2400, 77.4050, 'B-Sector, Shahpura, Bhopal', 'pending'),
        ('Sunil Mehta', '9844444444', 'carpentry', 23.2500, 77.4550, 'Sector-A, Indrapuri, Bhopal', 'completed')
        """)

    print("✅ Successfully seeded Local SQLite (sahakarsetu.db)!")


def main():
    db_url = os.environ.get("DATABASE_URL")
    if db_url and (db_url.startswith("postgres://") or db_url.startswith("postgresql://")):
        seed_postgres(db_url)
    else:
        seed_sqlite()

    print("----------------------------------------------------------------")
    print("🔑 DEMO ACCOUNTS READY (Password: demo1234)")
    print("   🏡 Ghar (Customer):  9876543210")
    print("   🔧 Kaam (Worker):    9876543211")
    print("   🏛️ Sabha (Council):  9876543212")
    print("----------------------------------------------------------------")


if __name__ == "__main__":
    main()
