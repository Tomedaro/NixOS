"""Unit tests for canonical schema-signature extraction (Milestone 2 6C1).

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


def raises(exc_type: type, fn, *a, **kw):
    try:
        fn(*a, **kw)
        check(f"{fn.__name__} raises {exc_type.__name__}", False)
    except exc_type:
        pass


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
check("35A.1 1 named index in interactions",
      any(ni.index_name == "interactions_active_deadline_idx"
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
check("35A.2 different spacing equal", _normalize_schema_sql(a) == _normalize_schema_sql(b))
check("35A.2 newline normalized equal", _normalize_schema_sql(c) == _normalize_schema_sql(a))
check("35A.2 identical equal", _normalize_schema_sql(a) == _normalize_schema_sql(d))

# Whitespace inside string literal preserved
e = "CREATE TABLE x (a TEXT CHECK (a IN ('a b')))"
f = "CREATE TABLE x (a TEXT CHECK (a IN ('a  b')))"
check("35A.2 literal whitespace preserved",
      _normalize_schema_sql(e) != _normalize_schema_sql(f))

# CHECK expression change
g = "CHECK (x > 0)"
h = "CHECK (x >= 0)"
check("35A.2 CHECK change unequal", _normalize_schema_sql(g) != _normalize_schema_sql(h))

# Keyword case change
i = "CREATE TABLE x (a INTEGER)"
j = "create table x (a integer)"
check("35A.2 keyword case unequal", _normalize_schema_sql(i) != _normalize_schema_sql(j))

# ASC vs DESC
k = "CREATE INDEX idx ON x(a ASC)"
l = "CREATE INDEX idx ON x(a DESC)"
check("35A.2 ASC vs DESC unequal", _normalize_schema_sql(k) != _normalize_schema_sql(l))

# BINARY vs NOCASE
m = "CREATE INDEX idx ON x(a COLLATE BINARY)"
n = "CREATE INDEX idx ON x(a COLLATE NOCASE)"
check("35A.2 BINARY vs NOCASE unequal", _normalize_schema_sql(m) != _normalize_schema_sql(n))

# Line comment preserved
o = "CREATE TABLE x (a INTEGER -- comment\n)"
p = "CREATE TABLE x (a INTEGER)"
check("35A.2 line comment makes unequal", _normalize_schema_sql(o) != _normalize_schema_sql(p))

# Block comment preserved
q = "CREATE TABLE x (a INTEGER /* comment */)"
check("35A.2 block comment makes unequal", _normalize_schema_sql(q) != _normalize_schema_sql(p))

# Unterminated quote
raises(KernelCorruptionError, _normalize_schema_sql, "CREATE TABLE x (a TEXT CHECK (a = 'unterminated)")
raises(KernelCorruptionError, _normalize_schema_sql, "CREATE TABLE x /* unterminated block")

# ===========================================================================
# 35A.3: same-count automatic-index difference
# ===========================================================================
print("=== 35A.3 automatic-index multiset ===")

c1 = _mk_mem_conn()
c1.execute("CREATE TABLE t1 (a INTEGER PRIMARY KEY, b INTEGER UNIQUE)")
c2 = _mk_mem_conn()
c2.execute("CREATE TABLE t2 (a INTEGER PRIMARY KEY, b TEXT UNIQUE)")

s1 = _schema_signature(c1)
s2 = _schema_signature(c2)

t1_idxes = [ai for t in s1.tables for ai in t.auto_indexes]
t2_idxes = [ai for t in s2.tables for ai in t.auto_indexes]
check("35A.3 both have 2 auto indexes", len(t1_idxes) == len(t2_idxes))
check("35A.3 auto-index multisets differ", s1 != s2)
c1.close(); c2.close()

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

check("35A.4 ASC vs DESC different", _schema_signature(c1) != _schema_signature(c2))
c1.close(); c2.close()

c3 = _mk_mem_conn()
c3.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c3.execute("CREATE INDEX idx1 ON t(a COLLATE BINARY)")
c4 = _mk_mem_conn()
c4.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c4.execute("CREATE INDEX idx1 ON t(a COLLATE NOCASE)")

check("35A.4 BINARY vs NOCASE different", _schema_signature(c3) != _schema_signature(c4))
c3.close(); c4.close()

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

# ===========================================================================
# 35A.7: expected-signature cache isolation
# ===========================================================================
print("=== 35A.7 cache isolation ===")

_expected_schema_signature.cache_clear()
_build_count = [0]
_orig_build = _build_expected_schema_signature

def _counting_build():
    _build_count[0] += 1
    return _orig_build()

import ai_system.task_initiation_store as _store
_store._build_expected_schema_signature = _counting_build
_store._expected_schema_signature.cache_clear()

s = _store._expected_schema_signature()
check("35A.7 first call builds", _build_count[0] == 1)
s2 = _store._expected_schema_signature()
check("35A.7 second call cached", _build_count[0] == 1)
s3 = _store._expected_schema_signature()
check("35A.7 third call cached", _build_count[0] == 1)

# Restore
_store._build_expected_schema_signature = _orig_build
_store._expected_schema_signature.cache_clear()

# ===========================================================================
# 35A.9: safe discovered names
# ===========================================================================
print("=== 35A.9 safe PRAGMA names ===")

c = _mk_mem_conn()
c.execute("CREATE TABLE t (x INTEGER)")
c.execute("CREATE INDEX \"weird''name\" ON t(x)")

sig = _schema_signature(c)
names = [ni.index_name for t in sig.tables for ni in t.named_indexes]
check("35A.9 weird name captured", any("weird" in n for n in names))
c.close()


# --- 35A.4 partial: named index partial vs nonpartial ---
c5 = _mk_mem_conn()
c5.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c5.execute("CREATE INDEX idx1 ON t(a) WHERE a IS NOT NULL")
c6 = _mk_mem_conn()
c6.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
c6.execute("CREATE INDEX idx1 ON t(a)")
check("35A.4 partial vs nonpartial different", _schema_signature(c5) != _schema_signature(c6))
c5.close(); c6.close()

# --- 35A.7 actual-signature cache isolation ---
_store._expected_schema_signature.cache_clear()
_canonical = _store._schema_signature(_mk_mem_conn())  # not cached, just an actual sig
# Alter schema and verify actual signature differs from expected
_c_alt = _mk_mem_conn()
_c_alt.execute("CREATE TABLE extra (x INTEGER)")
_alt_sig = _store._schema_signature(_c_alt)
check("35A.7 altered sig != canonical expected", _alt_sig != _store._expected_schema_signature())
_c_alt.close()
# Cache still contains expected, not actual
_c_ok = _mk_mem_conn()
for stmt in _SCHEMA_DDL_STATEMENTS: _c_ok.execute(stmt)
_c_ok.execute("PRAGMA user_version = 1")
_ok_sig = _store._schema_signature(_c_ok)
check("35A.7 canonical OK after alter", _ok_sig == _store._expected_schema_signature())
_c_ok.close()

# --- 35A.8 object inventory ---
_c_inv1 = _mk_mem_conn()
_c_inv1.execute("CREATE TABLE t (x INTEGER)")
_c_inv2 = _mk_mem_conn()
_c_inv2.execute("CREATE TABLE t (x INTEGER)")
_c_inv2.execute("CREATE VIEW v AS SELECT * FROM t")
check("35A.8 extra view -> different", _schema_signature(_c_inv1) != _schema_signature(_c_inv2))
_c_inv1.close(); _c_inv2.close()
_c_inv3 = _mk_mem_conn()
_c_inv3.execute("CREATE TABLE t (x INTEGER)")
_c_inv4 = _mk_mem_conn()
_c_inv4.execute("CREATE TABLE t (x INTEGER)")
_c_inv4.execute("CREATE TRIGGER tr AFTER INSERT ON t BEGIN SELECT 1; END")
check("35A.8 extra trigger -> different", _schema_signature(_c_inv3) != _schema_signature(_c_inv4))
_c_inv3.close(); _c_inv4.close()
# Extra table
_c_inv5 = _mk_mem_conn()
_c_inv5.execute("CREATE TABLE t (x INTEGER)")
_c_inv6 = _mk_mem_conn()
_c_inv6.execute("CREATE TABLE t (x INTEGER)")
_c_inv6.execute("CREATE TABLE extra (y INTEGER)")
check("35A.8 extra table -> different", _schema_signature(_c_inv5) != _schema_signature(_c_inv6))
_c_inv5.close(); _c_inv6.close()
# Extra named index
_c_inv7 = _mk_mem_conn()
_c_inv7.execute("CREATE TABLE t (x INTEGER)")
_c_inv8 = _mk_mem_conn()
_c_inv8.execute("CREATE TABLE t (x INTEGER)")
_c_inv8.execute("CREATE INDEX extra_idx ON t(x)")
check("35A.8 extra named index -> different", _schema_signature(_c_inv7) != _schema_signature(_c_inv8))
_c_inv7.close(); _c_inv8.close()
# ANALYZE does not change object inventory
_c_an1 = _mk_mem_conn()
_c_an1.execute("CREATE TABLE t (x INTEGER)")
_c_an1.execute("CREATE INDEX idx1 ON t(x)")
_c_an2 = _mk_mem_conn()
_c_an2.execute("CREATE TABLE t (x INTEGER)")
_c_an2.execute("CREATE INDEX idx1 ON t(x)")
_c_an2.execute("ANALYZE")
check("35A.8 ANALYZE does not change signature", _schema_signature(_c_an1) == _schema_signature(_c_an2))
_c_an1.close(); _c_an2.close()



# --- 35A.5 STRICT option ---
_c_str1 = _mk_mem_conn()
_c_str1.execute("CREATE TABLE t (x INTEGER) STRICT")
_c_str2 = _mk_mem_conn()
_c_str2.execute("CREATE TABLE t (x INTEGER)")
check("35A.5 STRICT vs non-STRICT different", _schema_signature(_c_str1) != _schema_signature(_c_str2))
_c_str1.close(); _c_str2.close()

# --- 35A.5 WITHOUT ROWID ---
_c_wr1 = _mk_mem_conn()
_c_wr1.execute("CREATE TABLE t (x INTEGER PRIMARY KEY) WITHOUT ROWID")
_c_wr2 = _mk_mem_conn()
_c_wr2.execute("CREATE TABLE t (x INTEGER PRIMARY KEY)")
check("35A.5 WITHOUT ROWID different", _schema_signature(_c_wr1) != _schema_signature(_c_wr2))
_c_wr1.close(); _c_wr2.close()

# --- 35A.6 table_list capability ---
_c_tl = _mk_mem_conn()
_c_tl.execute("CREATE TABLE t (x INTEGER)")
_sig_tl = _schema_signature(_c_tl)
check("35A.6 table_list_supported is bool", isinstance(_sig_tl.table_options.table_list_supported, bool))
_tl_entries = _sig_tl.table_options.entries
check("35A.6 table_list has entry for t", len(_tl_entries) >= 1 and _tl_entries[0][0] == "t")
if _sig_tl.table_options.table_list_supported and len(_tl_entries) > 0:
    _entry = _tl_entries[0]
    check("35A.6 ncol is 1", _entry[2] == 1)
    check("35A.6 wr is 0 or 1", _entry[3] in (0, 1))
    check("35A.6 strict is 0 or 1", _entry[4] in (0, 1))
_c_tl.close()
# ===========================================================================
# Summary
# ===========================================================================
print()
print(f"=== {PASSED} passed, {FAILED} failed ===")
if FAILED:
    raise SystemExit(1)
print("ALL PASS")
