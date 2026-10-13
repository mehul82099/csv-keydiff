# Contributing

Run `python3 -m unittest -v` before opening a pull request.

For a bug report, include:
- Python version and operating system.
- The exact command, exit code and expected behavior.
- Two small fictional CSVs that reproduce it. Never post customer data or secrets.

Keep runtime dependencies at zero. Add a regression test for behavior changes.
Preserve exact text values, explicit keys and fail-on-ambiguity behavior.
Propose large format or normalization changes in an issue first.

The JSON format is versioned by `format_version`. Document changes that affect
scripts. Do not add tracking, network calls, fabricated benchmarks or usage claims.
