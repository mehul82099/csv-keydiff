# csv-keydiff

**Compare CSV exports by identity, not line number. Stop when the data is ambiguous.**

A small, local Python CLI for checking inventory snapshots, customer exports and migration results. Reordered rows and columns don't create false changes. A repeated ID doesn't silently discard a record.

- No runtime dependencies, account, API key or network calls.
- Explicit single or composite keys: `--key warehouse --key sku`.
- Exact text comparison preserves `001`, `1.00`, case and whitespace.
- JSON report: added records, removed records, changed cells and schema changes.
- Rejects duplicate/blank keys, duplicate headers, ragged rows and CSV parser errors.
- Exit codes for scripts: **0** equal, **1** different, **2** invalid input or I/O error.

## Try it in a minute

Requires **Python 3.10+** and Git. No `pip install` needed.

```sh
git clone https://github.com/mehul82099/csv-keydiff.git
cd csv-keydiff
python3 csv_keydiff.py before.csv after.csv \
  --key warehouse --key sku --ignore updated_at
```

The included sample is fictional inventory data. Its rows and columns have been reordered. The report shows:

```text
Added:     jaipur / 003 (Cocoa)
Removed:   jaipur / 002 (Coffee)
Changed:   jaipur / 001, stock "12" -> "10"
Unchanged: delhi / 001
```

The actual command prints JSON, not the text above. See [demo-report.json](demo-report.json) for the complete expected output. Exit code **1 is expected**, because the snapshots differ.

Save a new report without overwriting an earlier one:

```sh
python3 csv_keydiff.py before.csv after.csv \
  --key warehouse --key sku --ignore updated_at --output report.json
```

`--output` refuses to overwrite any existing path, including an input file. Reports include raw values. Store them as carefully as the source exports.

## Other examples

Single identifier:

```sh
python3 csv_keydiff.py old-customers.csv new-customers.csv --key customer_id
```

Semicolon-separated files or tab-separated files:

```sh
python3 csv_keydiff.py old.csv new.csv --key id --delimiter ';'
python3 csv_keydiff.py old.tsv new.tsv --key id --delimiter '\t'
```

Ignore a noisy shared column (repeat `--ignore` for more):

```sh
python3 csv_keydiff.py old.csv new.csv --key id --ignore updated_at
```

Encoding and per-file row limit:

```sh
python3 csv_keydiff.py old.csv new.csv --key id --encoding cp1252 --max-rows 20000
python3 csv_keydiff.py --help
```

The default encoding is `utf-8-sig`: ordinary UTF-8 and Excel-style UTF-8 BOM headers both work. The same delimiter and encoding apply to both files. Use a header row in each.

## Rules that matter

| Condition | Behavior |
| --- | --- |
| Rows or headers reordered | No difference by itself |
| Duplicate complete key | Stop with both CSV record numbers; no first/last-row guess |
| Empty or whitespace-only key component | Stop |
| Key changes | One removal and one addition |
| `001` vs `1`, `1.0` vs `1.00` | Different strings |
| Spaces or letter case change | Different strings; no automatic normalization |
| Column added or removed | Report under `columns`; counts as a difference |
| Schema change only | Existing rows can be `unchanged` on shared cells; inspect `columns` too |
| `--ignore` | Skip cell comparison for that shared non-key column, but keep raw added/removed rows |
| Blank line or incorrect cell count | Stop; no silently skipped records |
| Quoted comma, escaped quote, multiline field | Parsed by Python's standard CSV reader |

Record numbers include the header as record 1. They are not physical line numbers when fields contain newlines. Parser errors instead name the physical line reached. Keys are exact header names. A header called `Order ID` is passed as `--key 'Order ID'`. A comma in a header name is fine: keys are repeated arguments, not comma-split text.

## Use from Python

```python
from csv_keydiff import load_table, compare

keys = ["warehouse", "sku"]
with open("before.csv", encoding="utf-8-sig", newline="") as f:
    before = load_table(f, keys, label="before")
with open("after.csv", encoding="utf-8-sig", newline="") as f:
    after = load_table(f, keys, label="after")
report = compare(before, after, keys, ignore=["updated_at"])
print(report["summary"])
```

Use the same key list to load both tables and compare them. CLI failures write diagnostics to stderr and do not print a partial JSON report.

## Why another CSV diff?

This is a focused alternative, not a claim that CSV comparison is new or that existing tools are broken today.

The problem is visible in public discussions:

- [Comparing CSVs when row order doesn't matter](https://stackoverflow.com/questions/5212444/python-comparing-two-csv-files-when-order-of-rows-doesnt-matter): exported rows can arrive in a different order, making positional comparisons unhelpful.
- [Duplicate-key ambiguity report](https://github.com/simonw/csv-diff/issues/31): a historical issue describes surprising results with duplicate keys and incomplete records. This tool rejects those inputs instead of choosing a match.
- [Comparison by identifier instead of line](https://stackoverflow.com/questions/58485384/how-to-compare-two-csv-files-according-to-a-specific-variable-not-line-by-line): illustrates the broader matching problem. Its irregular field/value layout is **not** a supported format here; this tool requires a rectangular headered CSV.

[simonw/csv-diff](https://github.com/simonw/csv-diff) is an established option with CSV/TSV/JSON support and human-readable output. Prefer it when those features fit your work. `csv-keydiff` deliberately keeps one file, no runtime dependencies, repeatable composite keys, strict ambiguity checks and JSON-only reports. It is an independent implementation; no upstream code was copied.

Parsing references: [Python CSV documentation](https://docs.python.org/3/library/csv.html) and [RFC 4180](https://www.rfc-editor.org/rfc/rfc4180). Python's `strict=True` is used, but this is **not a full RFC validator**.

## Tests

```sh
python3 -m unittest -v
```

39 offline tests cover reordering, composite keys, key collisions, added/removed/changed rows, schema differences, BOM decoding, quoting and multiline fields, Unicode, leading zeros, duplicate keys, malformed rows, limits, output protection and CLI exit codes. The permutation test checks 20 deterministic shuffled exports.

No performance benchmark or production deployment claim is made. Tests were run locally on Python 3.10.12; broader Python/platform compatibility is intended, not yet independently verified.

## Limits and privacy

- Both tables and the report are held in memory. Default limit: 100,000 data records per file. Wide files can still use substantial memory; this is not a streaming or billion-row tool.
- Python's CSV field-size limit applies. Very large individual fields can be rejected.
- No fuzzy matching, number/date conversion, tolerance, formulas, Excel workbooks or headerless files.
- This checks snapshots, not whether business data is correct. It does not reconcile payments or make financial decisions.
- No telemetry or upload code. JSON output can contain private customer data, so don't commit real exports or reports.
- Formula-like cells stay strings. Don't convert untrusted reports to spreadsheet formulas without safe handling.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Reproduce bugs with fictional data and include the Python version and exact command. Don't post secrets or customer exports.

## License

[MIT](LICENSE). Free to use, modify and redistribute under the license terms.
