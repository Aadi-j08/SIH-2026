"""
State-machine tests for the psycopg wrapper in app/pg.py.

The transaction handling, lastrowid recovery and BEGIN IMMEDIATE locking in
app/pg.py are where SQLite and PostgreSQL semantics differ, and none of it can
be exercised by the SQLite test suite. These drive the wrapper against a fake
driver that records the SQL sent, so the statements and the transaction
transitions are both asserted without a PostgreSQL server.

A review of the first cut of this branch found three defects on exactly these
paths (a non-atomic `connection()`, a session-scoped `lastval()`, and a
`BEGIN IMMEDIATE` that took no lock), all because nothing executed them.
"""
import pytest

from app import pg


class FakeCursor:
    def __init__(self, owner):
        self._owner = owner
        self._result = None
        self.description = None
        self.rowcount = -1

    def execute(self, sql, params=None):
        self._owner.executed.append((sql, params))
        self._result = self._owner.next_result
        if self._owner.next_result is not None:
            self.rowcount = 1
        else:
            self.rowcount = 0
        return self

    def executemany(self, sql, params):
        self._owner.executed.append((sql, params))
        return self

    def fetchone(self):
        result, self._result = self._result, None
        return result

    def fetchall(self):
        result, self._result = self._result, []
        return [result] if result else []

    def fetchmany(self, size=None):
        return []

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter([])


class FakeRaw:
    """Minimal stand-in for a psycopg connection."""

    def __init__(self, next_result=None):
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.autocommit = True
        self.row_factory = None
        self.next_result = next_result

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


@pytest.fixture
def conn():
    """A wrapper whose id-column lookups are pre-answered."""
    raw = FakeRaw()
    connection = pg.Connection(raw)
    connection._id_columns = {
        "workers": True,
        "users": True,
        "feedback": True,
        "sessions": False,
        "schema_migrations": False,
    }
    return connection


def sqls(conn):
    return [sql for sql, _ in conn._raw.executed]


# ── transactions ─────────────────────────────────────────────────────────────

def test_first_dml_opens_a_transaction(conn):
    """database.connection() must stay all-or-nothing, as SQLite's is.

    autocommit=True on the raw connection means psycopg never opens one on its
    own, so without this the block would autocommmit statement by statement and
    a signup failing on its second INSERT would leave the first row behind.
    """
    conn.execute("UPDATE workers SET status = ? WHERE id = ?", ("active", 1))

    assert sqls(conn) == ["BEGIN", "UPDATE workers SET status = %s WHERE id = %s"]
    assert conn.in_transaction is True


def test_reads_do_not_open_a_transaction(conn):
    conn.execute("SELECT 1 FROM workers WHERE id = ?", (1,))
    assert "BEGIN" not in sqls(conn)
    assert conn.in_transaction is False


def test_second_dml_reuses_the_open_transaction(conn):
    conn.execute("INSERT INTO users (portal) VALUES (?)", ("worker",))
    conn.execute("INSERT INTO feedback (body) VALUES (?)", ("hi",))
    assert sqls(conn).count("BEGIN") == 1


def test_commit_ends_the_transaction(conn):
    conn.execute("INSERT INTO users (portal) VALUES (?)", ("worker",))
    conn.commit()
    assert conn._raw.commits == 1
    assert conn.in_transaction is False


def test_commit_without_a_transaction_is_a_noop(conn):
    conn.commit()
    assert conn._raw.commits == 0


def test_rollback_ends_the_transaction(conn):
    conn.execute("INSERT INTO users (portal) VALUES (?)", ("worker",))
    conn.rollback()
    assert conn._raw.rollbacks == 1
    assert conn.in_transaction is False


def test_explicit_begin_and_commit_drive_the_state(conn):
    conn.execute("BEGIN")
    assert conn.in_transaction is True
    conn.execute("COMMIT")
    assert conn.in_transaction is False


def test_close_rolls_back_a_leaked_transaction(conn):
    """A pooled connection must not hand the next request a dirty transaction."""
    conn.execute("INSERT INTO users (portal) VALUES (?)", ("worker",))
    conn.close()
    assert conn._raw.rollbacks == 1
    assert conn.in_transaction is False


def test_executescript_runs_in_its_own_transaction(conn):
    conn.executescript("CREATE TABLE IF NOT EXISTS t (id SERIAL PRIMARY KEY);")
    assert sqls(conn)[0] == "BEGIN"
    assert conn._raw.commits == 1
    assert conn.in_transaction is False


def test_executescript_failure_rolls_back(conn):
    class Failing(FakeRaw):
        def cursor(self):
            class C(FakeCursor):
                def execute(self, sql, params=None):
                    if sql.startswith("CREATE"):
                        raise pg.psycopg.errors.SyntaxError("boom")
                    return super().execute(sql, params)

            return C(self)

    raw = Failing()
    connection = pg.Connection(raw)
    with pytest.raises(pg.sqlite3.OperationalError):
        connection.executescript("CREATE TABLE bad ();")
    assert raw.rollbacks == 1


# ── BEGIN IMMEDIATE ──────────────────────────────────────────────────────────

def test_begin_immediate_takes_a_write_lock(conn):
    """Plain BEGIN is deferred in PostgreSQL and locks nothing.

    SQLite's BEGIN IMMEDIATE grabs the writer lock before the first read, which
    is what stops two requests both reading 'pending' and assigning it twice.
    """
    conn.execute("BEGIN IMMEDIATE")

    statements = sqls(conn)
    assert statements[0] == "BEGIN"
    assert any("pg_advisory_xact_lock" in s for s in statements), (
        f"no write lock taken: {statements}"
    )
    assert conn.in_transaction is True


def test_advisory_lock_is_transaction_scoped(conn):
    """pg_advisory_xact_lock releases at COMMIT or ROLLBACK; a session lock would not."""
    conn.execute("BEGIN IMMEDIATE")
    assert any("pg_advisory_xact_lock" in s for s in sqls(conn))

    conn.execute("COMMIT")
    # xact-scoped means the lock went with the transaction; nothing to unlock.
    assert not any("pg_advisory_unlock" in s for s in sqls(conn))
    assert conn.in_transaction is False


# ── lastrowid ────────────────────────────────────────────────────────────────

def test_lastrowid_comes_from_returning_in_the_same_round_trip(conn):
    """lastval() is session-scoped and table-agnostic; on a pooled connection it
    returns another table's id from an earlier request. RETURNING avoids both
    that and the second round trip."""
    conn._raw.next_result = (42,)
    cursor = conn.execute("INSERT INTO workers (name) VALUES (?)", ("Meena",))

    statements = sqls(conn)
    assert statements[-1].endswith("RETURNING id")
    assert statements.count("BEGIN") == 1
    assert cursor.lastrowid == 42


def test_lastrowid_is_none_when_the_row_was_skipped(conn):
    """ON CONFLICT DO NOTHING inserts nothing, so there is no id to report."""
    conn._raw.next_result = None
    cursor = conn.execute("INSERT OR IGNORE INTO feedback (body) VALUES (?)", ("hi",))
    assert cursor.lastrowid is None


def test_no_returning_id_for_tables_without_an_id_column(conn):
    """sessions and schema_migrations have no id; appending it would be a syntax error."""
    cursor = conn.execute("INSERT INTO sessions (token) VALUES (?)", ("abc",))
    assert not sqls(conn)[-1].endswith("RETURNING id")
    assert cursor.lastrowid is None


def test_existing_returning_clause_is_not_duplicated(conn):
    conn._raw.next_result = (7,)
    conn.execute("INSERT INTO workers (name) VALUES (?) RETURNING id", ("Meena",))
    assert sqls(conn)[-1].count("RETURNING") == 1


def test_id_column_lookup_happens_once_per_table(conn):
    # Start from a cold cache: the fixture pre-answers the lookups.
    conn._id_columns = {}
    conn.execute("INSERT INTO workers (name) VALUES (?)", ("a",))
    conn.execute("INSERT INTO workers (name) VALUES (?)", ("b",))
    lookups = [s for s in sqls(conn) if "information_schema" in s]
    assert len(lookups) == 1, "the id-column lookup should be cached per connection"


def test_plain_select_does_not_set_lastrowid(conn):
    conn.execute("SELECT * FROM workers WHERE id = ?", (1,))
    assert conn.cursor().lastrowid is None
