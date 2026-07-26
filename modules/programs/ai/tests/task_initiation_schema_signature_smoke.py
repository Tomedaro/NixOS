"""Unit tests for canonical schema-signature extraction (Milestone 2 6C1b).

Does NOT test production enforcement.  All checks are extractor-only.
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from ai_system.task_initiation_store import (
    SchemaSignature, TableSignature, NamedIndexSignature,
    AutoIndexSignature, IndexColumnSignature, ForeignKeySignature,
    TableOptionsSignature,
    _schema_signature, _expected_schema_signature, _build_expected_schema_signature,
    _normalize_schema_sql, _sql_string_literal,
    _SCHEMA_DDL_STATEMENTS,
)
from ai_system.task_initiation_private import KernelCorruptionError

PASSED = 0
FAILED = 0


def check(description: str, condition: bool) -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
    else:
        FAILED += 1
        print(f"FAIL {description}")


def expect_raises(description: str, exc_type: type, fn, *a, **kw):
    try:
        fn(*a, **kw)
        check(description, False)
    except exc_type:
        check(description, True)


def _mk_mem_conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


# ===========================================================================
# 35A.1: canonical expected signature
# ===========================================================================
print("=== 35A.1 canonical expected signature ===")

conn = _mk_mem_conn()
for stmt in _SCHEMA_DDL_STATEMENTS:
    conn.execute(stmt)
conn.execute("PRAGMA user_version = 1")

actual = _schema_signature(conn)
expected = _expected_schema_signature()
check("35A.1 actual == expected", actual == expected)
check("35A.1 user_version == 1", actual.user_version == 1)
check("35A.1 3 tables", len(actual.tables) == 3)
check("35A.1 1 named index", any(
    ni.index_name == "interactions_active_deadline_idx"
    for t in actual.tables for ni in t.named_indexes))
conn.close()

# ===========================================================================
# 35A.2: conservative whitespace normalization
# ===========================================================================
print("=== 35A.2 whitespace normalization ===")

check("35A.2 None -> None", _normalize_schema_sql(None) is None)
check("35A.2 whitespace-only -> None", _normalize_schema_sql("   \n  ") is None)

a = "CREATE TABLE x ( a INTEGER PRIMARY KEY )"
b = "CREATE   TABLE   x   (   a   INTEGER   PRIMARY   KEY   )"
c = "CREATE TABLE x (\n  a INTEGER PRIMARY KEY\n)"
d = "CREATE TABLE x ( a INTEGER PRIMARY KEY )"
check("35A.2 diff spacing equal", _normalize_schema_sql(a) == _normalize_schema_sql(b))
check("35A.2 newline equal", _normalize_schema_sql(c) == _normalize_schema_sql(a))
check("35A.2 identical equal", _normalize_schema_sql(a) == _normalize_schema_sql(d))

e = "CREATE TABLE x (a TEXT CHECK (a IN ('a b')))"
f = "CREATE TABLE x (a TEXT CHECK (a IN ('a  b')))"
check("35A.2 literal whitespace preserved", _normalize_schema_sql(e) != _normalize_schema_sql(f))

g = "CHECK (x > 0)"
h = "CHECK (x >= 0)"
check("35A.2 CHECK change unequal", _normalize_schema_sql(g) != _normalize_schema_sql(h))

i = "CREATE TABLE x (a INTEGER)"
j = "create table x (a integer)"
check("35A.2 keyword case unequal", _normalize_schema_sql(i) != _normalize_schema_sql(j))

k = "CREATE INDEX idx ON x(a ASC)"
l = "CREATE INDEX idx ON x(a DESC)"
check("35A.2 ASC vs DESC unequal", _normalize_schema_sql(k) != _normalize_schema_sql(l))

m = "CREATE INDEX idx ON x(a COLLATE BINARY)"
n = "CREATE INDEX idx ON x(a COLLATE NOCASE)"
check("35A.2 BINARY vs NOCASE unequal", _normalize_schema_sql(m) != _normalize_schema_sql(n))

o = "CREATE TABLE x (a INTEGER -- comment\n)"
p = "CREATE TABLE x (a INTEGER)"
check("35A.2 comment unequal", _normalize_schema_sql(o) != _normalize_schema_sql(p))

q = "CREATE TABLE x (a INTEGER /* comment */)"
check("35A.2 block comment unequal", _normalize_schema_sql(q) != _normalize_schema_sql(p))

expect_raises("35A.2 unterminated quote", KernelCorruptionError,
              _normalize_schema_sql, "CREATE TABLE x (a TEXT CHECK (a = 'unterminated)")
expect_raises("35A.2 unterminated block comment", KernelCorruptionError,
              _normalize_schema_sql, "CREATE TABLE x /* unterminated block")

# ===========================================================================
# 35A.3: automatic-index semantic multiset
# ===========================================================================
print("=== 35A.3 automatic-index multiset ===")

# Same table name, same columns, different UNIQUE column
c1 = _mk_mem_conn()
c1.execute("CREATE TABLE t (a INTEGER PRIMARY KEY, b INTEGER UNIQUE, c INTEGER)")
c2 = _mk_mem_conn()
c2.execute("CREATE TABLE t (a INTEGER PRIMARY KEY, b INTEGER, c INTEGER UNIQUE)")

ai1 = _schema_signature(c1).tables[0].auto_indexes
ai2 = _schema_signature(c2).tables[0].auto_indexes
check("35A.3 equal auto-index count", len(ai1) == len(ai2))
check("35A.3 auto-index multisets differ", ai1 != ai2)
c1.close(); c2.close()

# Same column, different collation
c3 = _mk_mem_conn()
c3.execute("CREATE TABLE t (a INTEGER PRIMARY KEY, b TEXT UNIQUE COLLATE BINARY)")
c4 = _mk_mem_conn()
c4.execute("CREATE TABLE t (a INTEGER PRIMARY KEY, b TEXT UNIQUE COLLATE NOCASE)")

ai3 = _schema_signature(c3).tables[0].auto_indexes
ai4 = _schema_signature(c4).tables[0].auto_indexes
check("35A.3 collation: equal count", len(ai3) == len(ai4))
check("35A.3 collation: multisets differ", ai3 != ai4)
c3.close(); c4.close()

# ===========================================================================
# 35A.4: named index definition
# ===========================================================================
print("=== 35A.4 named index definition ===")

c1 = _mk_mem_conn()
c1.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c1.execute("CREATE INDEX idx1 ON t(a ASC)")
c2 = _mk_mem_conn()
c2.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c2.execute("CREATE INDEX idx1 ON t(a DESC)")
check("35A.4 ASC vs DESC", _schema_signature(c1) != _schema_signature(c2))
c1.close(); c2.close()

c3 = _mk_mem_conn()
c3.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c3.execute("CREATE INDEX idx1 ON t(a COLLATE BINARY)")
c4 = _mk_mem_conn()
c4.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c4.execute("CREATE INDEX idx1 ON t(a COLLATE NOCASE)")
check("35A.4 BINARY vs NOCASE", _schema_signature(c3) != _schema_signature(c4))
c3.close(); c4.close()

c5 = _mk_mem_conn()
c5.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c5.execute("CREATE INDEX idx1 ON t(a) WHERE a IS NOT NULL")
c6 = _mk_mem_conn()
c6.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c6.execute("CREATE INDEX idx1 ON t(a)")
check("35A.4 partial vs nonpartial", _schema_signature(c5) != _schema_signature(c6))
c5.close(); c6.close()

# ===========================================================================
# 35A.5: table definition and options
# ===========================================================================
print("=== 35A.5 table definition ===")

c1 = _mk_mem_conn()
c1.execute("CREATE TABLE t (a INTEGER CHECK (a > 0))")
c2 = _mk_mem_conn()
c2.execute("CREATE TABLE t (a INTEGER CHECK (a >= 0))")
check("35A.5 CHECK different", _schema_signature(c1) != _schema_signature(c2))
c1.close(); c2.close()

c3 = _mk_mem_conn()
c3.execute("CREATE TABLE t (a INTEGER DEFAULT 1)")
c4 = _mk_mem_conn()
c4.execute("CREATE TABLE t (a INTEGER DEFAULT 0)")
check("35A.5 DEFAULT different", _schema_signature(c3) != _schema_signature(c4))
c3.close(); c4.close()

c5 = _mk_mem_conn()
c5.execute("CREATE TABLE t (x INTEGER) STRICT")
c6 = _mk_mem_conn()
c6.execute("CREATE TABLE t (x INTEGER)")
check("35A.5 STRICT vs non-STRICT", _schema_signature(c5) != _schema_signature(c6))
c5.close(); c6.close()

c7 = _mk_mem_conn()
c7.execute("CREATE TABLE t (x INTEGER PRIMARY KEY) WITHOUT ROWID")
c8 = _mk_mem_conn()
c8.execute("CREATE TABLE t (x INTEGER PRIMARY KEY)")
check("35A.5 WITHOUT ROWID", _schema_signature(c7) != _schema_signature(c8))
c7.close(); c8.close()

# FK deferrability
c9 = _mk_mem_conn()
c9.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
c9.execute("CREATE TABLE child (pid INTEGER REFERENCES parent(id))")
c10 = _mk_mem_conn()
c10.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
c10.execute("CREATE TABLE child (pid INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED)")
check("35A.5 FK deferrability", _schema_signature(c9) != _schema_signature(c10))
c9.close(); c10.close()

# ===========================================================================
# 35A.6: table_list capability
# ===========================================================================
print("=== 35A.6 table_list capability ===")

c = _mk_mem_conn()
c.execute("CREATE TABLE t (x INTEGER)")
sig = _schema_signature(c)
check("35A.6 supported is bool", isinstance(sig.table_options.table_list_supported, bool))
entries = sig.table_options.entries
check("35A.6 has entry for t", len(entries) >= 1 and entries[0][0] == "t")
if sig.table_options.table_list_supported and len(entries) > 0:
    e = entries[0]
    check("35A.6 ncol is 1", e[2] == 1)
    check("35A.6 wr is 0/1", e[3] in (0, 1))
    check("35A.6 strict is 0/1", e[4] in (0, 1))
c.close()

# table_list error propagation
import sqlite3 as _sq
class _ErrProxy:
    def __init__(self, real):
        object.__setattr__(self, '_r', real)
    def __getattr__(self, n):
        return getattr(object.__getattribute__(self, '_r'), n)
    def execute(self, sql, *a):
        if 'PRAGMA main.table_list' in str(sql):
            _e = _sq.OperationalError("injected table_list failure")
            _e.sqlite_errorcode = _sq.SQLITE_IOERR
            raise _e
        return object.__getattribute__(self, '_r').execute(sql, *a)
c2 = _mk_mem_conn()
c2.execute("CREATE TABLE t (x INTEGER)")
proxy = _ErrProxy(c2)
expect_raises("35A.6 table_list error propagates", _sq.OperationalError,
              _schema_signature, proxy)
c2.close()

# ===========================================================================
# 35A.7: expected-signature cache isolation
# ===========================================================================
print("=== 35A.7 cache isolation ===")

import ai_system.task_initiation_store as _store
_store._expected_schema_signature.cache_clear()
_build_count = [0]
_orig_build = _build_expected_schema_signature

def _counting_build():
    _build_count[0] += 1
    return _orig_build()

_store._build_expected_schema_signature = _counting_build
_store._expected_schema_signature.cache_clear()

s = _store._expected_schema_signature()
check("35A.7 first call builds", _build_count[0] == 1)
s2 = _store._expected_schema_signature()
check("35A.7 second call cached", _build_count[0] == 1)
s3 = _store._expected_schema_signature()
check("35A.7 third call cached", _build_count[0] == 1)

_store._build_expected_schema_signature = _orig_build
_store._expected_schema_signature.cache_clear()

# Actual altered schema must differ from expected
c_alt = _mk_mem_conn()
c_alt.execute("CREATE TABLE extra (x INTEGER)")
alt_sig = _store._schema_signature(c_alt)
check("35A.7 altered != expected", alt_sig != _store._expected_schema_signature())
c_alt.close()

# Canonical OK after alter
c_ok = _mk_mem_conn()
for stmt in _SCHEMA_DDL_STATEMENTS: c_ok.execute(stmt)
c_ok.execute("PRAGMA user_version = 1")
check("35A.7 canonical OK after alter", _schema_signature(c_ok) == _store._expected_schema_signature())
c_ok.close()

# ===========================================================================
# 35A.8: object inventory
# ===========================================================================
print("=== 35A.8 object inventory ===")

c1 = _mk_mem_conn(); c1.execute("CREATE TABLE t (x INTEGER)")
c2 = _mk_mem_conn(); c2.execute("CREATE TABLE t (x INTEGER)")
c2.execute("CREATE VIEW v AS SELECT * FROM t")
check("35A.8 extra view", _schema_signature(c1) != _schema_signature(c2))
c1.close(); c2.close()

c3 = _mk_mem_conn(); c3.execute("CREATE TABLE t (x INTEGER)")
c4 = _mk_mem_conn(); c4.execute("CREATE TABLE t (x INTEGER)")
c4.execute("CREATE TRIGGER tr AFTER INSERT ON t BEGIN SELECT 1; END")
check("35A.8 extra trigger", _schema_signature(c3) != _schema_signature(c4))
c3.close(); c4.close()

c5 = _mk_mem_conn(); c5.execute("CREATE TABLE t (x INTEGER)")
c6 = _mk_mem_conn(); c6.execute("CREATE TABLE t (x INTEGER)")
c6.execute("CREATE TABLE extra (y INTEGER)")
check("35A.8 extra table", _schema_signature(c5) != _schema_signature(c6))
c5.close(); c6.close()

c7 = _mk_mem_conn(); c7.execute("CREATE TABLE t (x INTEGER)")
c8 = _mk_mem_conn(); c8.execute("CREATE TABLE t (x INTEGER)")
c8.execute("CREATE INDEX extra_idx ON t(x)")
check("35A.8 extra named index", _schema_signature(c7) != _schema_signature(c8))
c7.close(); c8.close()

c9 = _mk_mem_conn(); c9.execute("CREATE TABLE t (x INTEGER)")
c9.execute("CREATE INDEX idx1 ON t(x)")
c10 = _mk_mem_conn(); c10.execute("CREATE TABLE t (x INTEGER)")
c10.execute("CREATE INDEX idx1 ON t(x)")
c10.execute("ANALYZE")
check("35A.8 ANALYZE unchanged", _schema_signature(c9) == _schema_signature(c10))
c9.close(); c10.close()

# ===========================================================================
# 35A.9: safe discovered names
# ===========================================================================
print("=== 35A.9 safe PRAGMA names ===")

c = _mk_mem_conn()
c.execute("CREATE TABLE t (x INTEGER)")
c.execute("CREATE INDEX [weird'name] ON t(x)")
sig = _schema_signature(c)
names = [ni.index_name for t in sig.tables for ni in t.named_indexes]
check("35A.9 weird name captured", any("weird" in n for n in names))
c.close()

# ===========================================================================
# 35A.10: DDL immutability
# ===========================================================================
print("=== 35A.10 DDL immutability ===")

check("35A.10 _SCHEMA_DDL_STATEMENTS is tuple", isinstance(_SCHEMA_DDL_STATEMENTS, tuple))
check("35A.10 has 4 statements", len(_SCHEMA_DDL_STATEMENTS) == 4)

# ===========================================================================
# Summary
# ===========================================================================
print()
print(f"=== {PASSED} passed, {FAILED} failed ===")
if FAILED:
    raise SystemExit(1)
print("ALL PASS")
