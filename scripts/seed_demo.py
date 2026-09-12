"""
Seed a realistic demo cooperative into the database.

    .venv\\Scripts\\python scripts\\seed_demo.py            # into the DB the app uses (SAHAKARSETU_DB or sahakarsetu.db)
    .venv\\Scripts\\python scripts\\seed_demo.py --db demo.db

Creates, through the app's own code paths (so every rule applies):
  52 workers with Kaam accounts, 76 households with Ghar accounts, 14 council
  accounts, ~430 bookings spread over the last 90 days — assigned by the real
  allocation engine, completed with 85/10/5 ledger entries, mostly rated —
  plus a handful of disputes. Timestamps are back-dated so month-over-month
  figures, response times and "unassigned for 2 hours" all mean something.

Every demo account's password is  demo1234 . Phones: customers 90000001xx,
workers 90000002xx, council 90000003xx. Refuses to run twice on the same DB.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

parser = argparse.ArgumentParser()
parser.add_argument("--db", help="SQLite file to seed (default: what the app uses)")
parser.add_argument("--seed", type=int, default=2026)
args = parser.parse_args()
if args.db:
    os.environ["SAHAKARSETU_DB"] = str(Path(args.db).resolve())

from app import auth, database, repository  # noqa: E402
from app.booking_flow_db import booking_flow_connection  # noqa: E402
from app.cooperative import CooperativeUpdate, update_cooperative  # noqa: E402
from app.schemas import AvailabilityWindow, BookingCreate  # noqa: E402
from app.services import booking_flow  # noqa: E402

rng = random.Random(args.seed)
PASSWORD = "demo1234"
NOW = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
SITE = (23.2599, 77.4126)   # Bhopal

FIRST_M = ["Ravi", "Imran", "Karan", "Suresh", "Mohan", "Arjun", "Deepak", "Vikram", "Sanjay", "Rahul", "Amit", "Rajesh",
           "Manoj", "Naveen", "Prakash", "Sunil", "Vinod", "Ashok", "Dinesh", "Ganesh", "Harish", "Kamal", "Lokesh", "Nitin"]
FIRST_F = ["Meena", "Asha", "Anjali", "Sunita", "Priya", "Kavita", "Pooja", "Rekha", "Seema", "Neha", "Geeta", "Lata",
           "Radha", "Sarita", "Shobha", "Usha", "Vandana", "Nisha", "Ritu", "Sapna"]
LAST = ["Kumar", "Devi", "Sharma", "Singh", "Verma", "Sheikh", "Yadav", "Patel", "Gupta", "Mishra", "Rajput", "Ahirwar",
        "Chouhan", "Malviya", "Sahu", "Prajapati", "Khan", "Lodhi", "Dubey", "Tiwari"]
LOCALITIES = ["Arera Colony", "MP Nagar", "Kolar Road", "Shahpura", "Bairagarh", "TT Nagar", "Ashoka Garden", "Habibganj",
              "Ayodhya Bypass", "Misrod", "Hoshangabad Road", "Lalghati", "Berasia Road", "Karond", "Chunabhatti", "Bawadiya Kalan"]
TRADE_COUNTS = {"plumbing": 12, "electrical": 9, "cleaning": 14, "carpentry": 8, "painting": 9}
TRADE_WEIGHT = {"plumbing": 30, "electrical": 24, "cleaning": 28, "carpentry": 9, "painting": 9}
TRADE_BILL = {"plumbing": (400, 1800), "electrical": (350, 2200), "cleaning": (500, 1500), "carpentry": (800, 3500), "painting": (1500, 6000)}
COUNCIL = [("Rajesh Iyer", "Secretary"), ("Sunita Malviya", "President"), ("Imran Sheikh", "Treasurer"), ("Kavita Sahu", "Coordinator")] + \
          [(None, "Member")] * 10
DISPUTE_TEXTS = {
    "payment": ["Bill higher than the quoted amount", "Customer paid less than the entered bill", "Material cost was not agreed beforehand"],
    "quality": ["Leak came back the next day", "Switchboard still trips", "Cleaning missed the kitchen", "Door does not close properly"],
    "other": ["Worker arrived two hours late", "Booking was for a different address"],
}


def stamp(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M:%S")


def name(female: bool | None = None) -> str:
    if female is None:
        female = rng.random() < 0.45
    return f"{rng.choice(FIRST_F if female else FIRST_M)} {rng.choice(LAST)}"


def near(spread: float = 0.06) -> tuple[float, float]:
    return round(SITE[0] + rng.uniform(-spread, spread), 5), round(SITE[1] + rng.uniform(-spread, spread), 5)


def signup(**body) -> auth.User:
    return auth.signup(auth.SignupRequest(password=PASSWORD, **body))


def run(sql: str, params: tuple = ()) -> None:
    with database.connection() as conn:
        conn.execute(sql, params)


def main() -> None:
    database.init_db()
    with database.connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE phone = '9000000100'").fetchone():
            sys.exit(f"{database.DB_PATH} already holds the demo data; use --db for a fresh file.")
    print(f"Seeding {database.DB_PATH}")

    # cooperative -------------------------------------------------------------
    update_cooperative(CooperativeUpdate(secretary="Rajesh Iyer", coordinator="Kavita Sahu", last_meeting="2026-09-04"))

    # council -----------------------------------------------------------------
    for i, (person, role) in enumerate(COUNCIL):
        signup(portal="sabha", name=person or name(), phone=f"90000003{i:02d}", role=role, council_code=auth.council_code())

    # workers -----------------------------------------------------------------
    workers: list[auth.User] = []
    i = 0
    for trade, count in TRADE_COUNTS.items():
        for _ in range(count):
            lat, lon = near()
            workers.append(signup(
                portal="kaam", name=name(female=trade == "cleaning" and rng.random() < 0.7), phone=f"90000002{i:02d}",
                trade=trade, latitude=lat, longitude=lon, locality=rng.choice(LOCALITIES), languages=rng.choice([["hi"], ["hi", "en"], ["hi", "mr"]]),
            ))
            i += 1
    # base ratings and a joining date spread over the year
    for w in workers:
        rating = round(rng.uniform(3.6, 4.9), 1)
        joined = NOW - dt.timedelta(days=rng.randint(20, 300))
        run("UPDATE workers SET rating = ?, created_at = ? WHERE id = ?", (rating, stamp(joined), w.worker_id))
    # Kaam sign-ups wait for council approval; the cooperative approved everyone but the three newest
    for w in workers[:-3]:
        run("UPDATE workers SET status = 'active' WHERE id = ?", (w.worker_id,))
    # availability: most say nothing; some declare today; five declare themselves busy today (offline)
    today = (NOW + dt.timedelta(hours=5, minutes=30)).date()   # IST, like the app judges availability
    for w in rng.sample(workers, 5):
        repository.set_worker_availability(w.worker_id, [AvailabilityWindow(date=today, start="00:00", end="23:59", available=False)])
    for w in rng.sample([w for w in workers], 12):
        repository.set_worker_availability(w.worker_id, [AvailabilityWindow(weekday=d, start="08:00", end="18:00", available=True) for d in range(7)])

    # customers ---------------------------------------------------------------
    customers = [signup(portal="ghar", name=name(), phone=f"90000001{i:02d}", locality=rng.choice(LOCALITIES)) for i in range(76)]
    # a repeat-customer core: 68% book more than once
    regulars = rng.sample(customers, 52)

    # bookings ----------------------------------------------------------------
    trades = list(TRADE_WEIGHT)
    weights = [TRADE_WEIGHT[t] for t in trades]
    created: list[tuple[int, str, dt.datetime, dt.datetime, auth.User]] = []   # id, trade, created, scheduled, customer

    def place(customer: auth.User, trade: str, created_at: dt.datetime, hours_ahead: float) -> int:
        lat, lon = near(0.05)
        scheduled = created_at + dt.timedelta(hours=hours_ahead)
        b = repository.create_booking(BookingCreate(
            customer_name=customer.name, customer_phone=customer.phone, trade=trade, latitude=lat, longitude=lon,
            address=f"{rng.randint(2, 180)}, {customer.locality}, Bhopal", scheduled_for=scheduled,
        ))
        run("UPDATE bookings SET customer_user_id = ?, created_at = ? WHERE id = ?", (customer.id, stamp(created_at), b.id))
        created.append((b.id, trade, created_at, scheduled, customer))
        return b.id

    # 410 completed jobs over the last 90 days, weekday-weighted (Sat/Sun busier)
    completed_ids: list[int] = []
    for _ in range(410):
        days_ago = rng.randint(2, 90)
        day = today - dt.timedelta(days=days_ago)
        if day.weekday() >= 5 and rng.random() < 0.15:
            day -= dt.timedelta(days=rng.randint(1, 4))
        created_at = dt.datetime(day.year, day.month, day.day, rng.randint(7, 20), rng.randint(0, 59))
        customer = rng.choice(regulars) if rng.random() < 0.8 else rng.choice(customers)
        completed_ids.append(place(customer, rng.choices(trades, weights)[0], created_at, rng.uniform(2, 36)))
    # a few finished earlier today, so "completed today" is not zero
    for _ in range(6):
        created_at = NOW - dt.timedelta(hours=rng.uniform(5, 14))
        completed_ids.append(place(rng.choice(regulars), rng.choices(trades, weights)[0], created_at, rng.uniform(1, 2)))
    # 12 ongoing (assigned, scheduled today/tomorrow) and 8 unassigned (3 of them older than 2 hours)
    ongoing_ids = [place(rng.choice(customers), rng.choices(trades, weights)[0], NOW - dt.timedelta(hours=rng.uniform(1, 20)), rng.uniform(1, 30)) for _ in range(12)]
    pending_ids = [place(rng.choice(customers), rng.choices(trades, weights)[0], NOW - dt.timedelta(hours=rng.uniform(2.5, 6)), rng.uniform(2, 24)) for _ in range(3)]
    pending_ids += [place(rng.choice(customers), "electrical" if k < 3 else rng.choices(trades, weights)[0], NOW - dt.timedelta(minutes=rng.uniform(5, 100)), rng.uniform(2, 24)) for k in range(5)]
    by_id = {row[0]: row for row in created}

    # assign with the real engine, then back-date the assignment to 5–40 minutes after the booking
    def assign(booking_id: int) -> int | None:
        try:
            with booking_flow_connection() as conn:
                result = booking_flow.assign_booking(conn, booking_id)
        except booking_flow.BookingFlowError as exc:
            print("  could not assign", booking_id, exc)
            return None
        created_at = by_id[booking_id][2] + dt.timedelta(minutes=rng.uniform(5, 40))
        run("UPDATE assignments SET created_at = ? WHERE booking_id = ?", (stamp(created_at), booking_id))
        return result["worker"]["id"]

    print("  assigning", len(completed_ids) + len(ongoing_ids), "bookings with the allocation engine…")
    for booking_id in completed_ids + ongoing_ids:
        assign(booking_id)
        # keep the fairness counter from ballooning over 90 days of history
        run("UPDATE workers SET jobs_this_week = 0")

    # complete the historical ones: bill, ledger, timestamps, ratings
    print("  completing", len(completed_ids), "jobs…")
    for booking_id in completed_ids:
        _, trade, _, scheduled, _ = by_id[booking_id]
        lo, hi = TRADE_BILL[trade]
        amount = int(round(rng.uniform(lo, hi) / 50) * 50)
        with booking_flow_connection() as conn:
            try:
                booking_flow.complete_booking(conn, booking_id, amount)
            except booking_flow.BookingFlowError:
                continue
        done_at = min(scheduled + dt.timedelta(hours=rng.uniform(1, 3)), NOW - dt.timedelta(minutes=5))
        run("UPDATE bookings SET completed_at = ? WHERE id = ?", (stamp(done_at), booking_id))
        run("UPDATE payment_ledger SET created_at = ? WHERE booking_id = ?", (stamp(done_at), booking_id))
        if rng.random() < 0.72:
            stars = rng.choices([5, 4, 3, 2], [55, 32, 9, 4])[0]
            with booking_flow_connection() as conn:
                booking_flow.rate_booking(conn, booking_id, stars, rng.choice([None, None, "Good work", "On time", "Would book again", "Took longer than expected"]))
            run("UPDATE booking_ratings SET created_at = ? WHERE booking_id = ?", (stamp(done_at + dt.timedelta(hours=rng.uniform(1, 30))), booking_id))

    # this week's workload: count assignments since Monday, then push a few workers near the limit
    monday = dt.datetime.combine(today - dt.timedelta(days=today.weekday()), dt.time())
    with database.connection() as conn:
        counts = {r["worker_id"]: r["n"] for r in conn.execute(
            "SELECT worker_id, COUNT(*) AS n FROM assignments WHERE created_at >= ? GROUP BY worker_id", (stamp(monday),))}
        for w in workers:
            conn.execute("UPDATE workers SET jobs_this_week = ? WHERE id = ?", (counts.get(w.worker_id, 0), w.worker_id))
        busy = rng.sample([w.worker_id for w in workers], 4)
        for k, worker_id in enumerate(busy):
            conn.execute("UPDATE workers SET jobs_this_week = ? WHERE id = ?", (6 if k == 0 else 5, worker_id))

    # disputes: 3 open, 18 resolved
    print("  raising disputes…")
    disputed = rng.sample(completed_ids, 21)
    with database.connection() as conn:
        for k, booking_id in enumerate(disputed):
            open_ = k < 3
            kind = ["payment", "quality", "other"][k] if open_ else rng.choices(["payment", "quality", "other"], [5, 4, 1])[0]
            _, trade, _, scheduled, customer = by_id[booking_id]
            raised_by = ("customer" if k < 2 else "worker") if open_ else ("customer" if rng.random() < 0.75 else "worker")
            raiser_id = customer.id if raised_by == "customer" else None
            amount = int(rng.uniform(150, 900)) * 100 if kind == "payment" else None
            raised_at = scheduled + dt.timedelta(hours=rng.uniform(4, 48))
            conn.execute(
                "INSERT INTO disputes (booking_id, kind, raised_by, raised_by_user_id, amount_paise, description, status, resolution, created_at, resolved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (booking_id, kind, raised_by, raiser_id, amount, rng.choice(DISPUTE_TEXTS[kind]), "open" if open_ else "resolved",
                 None if open_ else rng.choice(["Worker revisited and fixed it free of charge", "Bill corrected to the quoted amount",
                                                "Partial refund of ₹200 agreed by both sides", "Explained; customer satisfied"]),
                 stamp(NOW - dt.timedelta(hours=rng.uniform(3, 40)) if open_ else raised_at),
                 None if open_ else stamp(raised_at + dt.timedelta(hours=rng.uniform(6, 72)))),
            )

    with database.connection() as conn:
        summary = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "workers", "bookings", "assignments", "payment_ledger", "disputes")}
    print("Done:", json.dumps(summary))
    print(f"Sign in as council: phone 9000000300 / {PASSWORD}   (customer 9000000100, worker 9000000200)")


if __name__ == "__main__":
    main()
