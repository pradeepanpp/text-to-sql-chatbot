"""
Evaluation metrics for Text-to-SQL.

Execution accuracy (EX) — the standard Text-to-SQL metric (Spider, BIRD):
run the generated SQL and the reference SQL on the same database and
compare the RESULTS, not the SQL text. Two different queries that return
the same rows are both correct.

How results are compared here:
  - Row order is ignored (rows compared as a multiset). Spider does the
    same unless the gold query has ORDER BY; we ignore order always,
    because most questions in this set do not ask for an order.
  - Column order and column names are ignored: a column mapping is
    searched for (SELECT a, b  ==  SELECT b AS x, a AS y).
  - Numbers are rounded to 2 decimals before comparing, so
    ROUND(x, 2) and x match.

Two levels:
  strict   — same number of columns, same rows.
  lenient  — the generated result may have EXTRA columns, as long as the
             reference columns are all present with the same rows
             (e.g. "SELECT * FROM products" vs "SELECT product_name").

Also here: Wilson score interval, for honest confidence intervals on
small samples (it behaves well near 0% and 100%, unlike p ± 1.96·SE).
"""

import math
from collections import Counter


def normalize_value(value):
    """Make values comparable: round numbers, strip strings."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        rounded = round(float(value), 2)
        return 0.0 if rounded == 0 else rounded     # avoid -0.0 vs 0.0
    if isinstance(value, bytes):
        return value
    text = str(value).strip()
    try:  # "12.50" vs 12.5
        return normalize_value(float(text))
    except ValueError:
        return text


def _normalize_rows(rows: list) -> list:
    return [tuple(normalize_value(v) for v in row) for row in rows]


def _column(rows: list, index: int) -> Counter:
    return Counter(row[index] for row in rows)


def results_match(
    reference_rows: list,
    generated_rows: list,
    allow_extra_columns: bool = False,
) -> bool:
    """
    True if the generated result contains the same rows as the reference,
    under some mapping of reference columns to generated columns.
    """
    ref = _normalize_rows(reference_rows)
    gen = _normalize_rows(generated_rows)

    if len(ref) != len(gen):
        return False
    if not ref:
        return True                                 # both empty

    n_ref, n_gen = len(ref[0]), len(gen[0])
    if n_gen < n_ref or (n_gen != n_ref and not allow_extra_columns):
        return False

    # Candidate generated columns for each reference column:
    # same multiset of values.
    gen_columns = [_column(gen, j) for j in range(n_gen)]
    candidates = []
    for i in range(n_ref):
        ref_col = _column(ref, i)
        options = [j for j in range(n_gen) if gen_columns[j] == ref_col]
        if not options:
            return False
        candidates.append(options)

    target = Counter(ref)

    # Backtracking search for an injective column mapping whose
    # projected rows match the reference rows exactly.
    def search(i: int, used: tuple) -> bool:
        if i == n_ref:
            projected = Counter(tuple(row[j] for j in used) for row in gen)
            return projected == target
        for j in candidates[i]:
            if j not in used and search(i + 1, used + (j,)):
                return True
        return False

    return search(0, ())


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple:
    """95% Wilson score interval for a proportion, as (low, high) in [0, 1]."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (
        round(max(0.0, (centre - margin) / denom), 4),
        round(min(1.0, (centre + margin) / denom), 4),
    )
