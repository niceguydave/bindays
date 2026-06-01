# Bindays

Tells you which bins go out and when.  I'm using Glasgow City Council as the test 
case, but I imagine this could be used for any other council in future.

This is the first commit which should prove that we can reliably fetch and parse the council's
collection calendar and print upcoming collections.

### Data source & acknowledgement

All collection data comes from **Glasgow City Council's** public bin-collection
pages: <https://www.glasgow.gov.uk/article/1524/Bin-Collection-Days>. This is an
unofficial, read-only tool — it is **not affiliated with or endorsed by Glasgow
City Council**. It simply reads the same publicly available pages you would, and
caches the result so it doesn't hammer their (slow) server. All credit for the
underlying data goes to GCC.

### Supported councils (and adding more)

Right now this tool supports **Glasgow City Council only**.

- `bindays/council.py` defines the `Council` interface (no council specifics).
- `bindays/councils/` holds the concrete providers and the registry
  `SUPPORTED_COUNCILS`, which today contains a **single** entry: Glasgow.
  `get_council()` raises a clear error for any unsupported council.
- The CLI and cache only ever talk to a `Council` provider, never to a council
  directly.
- All GCC-specific code lives under `bindays/councils/glasgow/` (`calendar.py`
  for the HTML calendar, `uprn.py` for the address search) and says so in its
  module docstrings.

Other councils publish this data very differently (some have APIs, some don't use
UPRNs at all). To add one later, create a new provider under `bindays/councils/`
that implements the `Council` interface and register it in `SUPPORTED_COUNCILS` —
no changes to the CLI or cache required.

## Quick start

**Requires Python 3.11+** (developed and tested on 3.13). The required version is
declared once, authoritatively, in `pyproject.toml` (`requires-python`).

```bash
# 1. Get the project ready (one time)
cd bindays
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # exact, pinned versions (see "Keeping dependencies up to date")

# 2. Find and save your property (one time)
python bin_check.py setup           # asks for your postcode, then saves it
#   or pass it directly:
python bin_check.py setup "G1 1RX"

# 3. Check your bins (any time)
python bin_check.py                 # next 4 weeks
python bin_check.py --weeks 8       # look further ahead
```

That's it. After `setup`, you never need to remember a UPRN or set any
environment variables.

### What `setup` does

1. Searches the council's address list for your postcode/address (a few seconds).
2. If more than one address matches, it lists them and asks you to pick yours.
3. Looks up that property's **UPRN** and saves it to `config.json` in this folder.

> Tip: a bare postcode lists every address on the street (the tool pages through
> all council results automatically), so just pick yours from the numbered list.
> A precise search like `"231 George Street"` narrows it to a single result. The
> council's server is slow, so each step takes a few seconds — the tool prints
> progress so you can tell it's working, not stuck.

## How it works

The council has no official API. Each property has a 12-digit **UPRN** (Unique
Property Reference Number). The collection calendar for a UPRN is an HTML page we
fetch and parse into a clean list of `(date, bin)` events. Every feature is built
on top of that list.

Bins:

| Colour | Contents |
|--------|----------|
| Blue   | Paper, card, cans, plastic bottles |
| Green  | General (non-recyclable) waste |
| Grey   | Food waste |
| Purple | Glass |
| Brown  | Garden waste (and food via compostable liners) |

## Speed: caching

The collection schedule changes maybe once or twice a year, but the council's
server is slow. So the first lookup fetches and parses the calendar, then saves
the result to `cache.json`. After that, checking your bins is **near-instant** —
it reads the cache instead of hitting the network.

- The cache auto-refreshes when it's older than 7 days (change with `--max-age-days N`).
- Force an immediate re-fetch any time with `--refresh`.
- If the council site is ever down, you still get an answer: the tool falls back
  to the last cached copy and tells you it's showing older data.

```bash
python bin_check.py                  # instant after the first run
python bin_check.py --refresh        # force a fresh fetch now
python bin_check.py --max-age-days 30  # only re-fetch if older than 30 days
```

## Advanced / overrides

You normally won't need these — `setup` handles everything.

```bash
# Use a specific UPRN without saving it:
python bin_check.py --uprn <your-uprn>

# Or via environment variable:
export BINDAYS_UPRN=<your-uprn>
python bin_check.py
```

Property lookup order: `--uprn` > `BINDAYS_UPRN` env var > saved `config.json`.

## Keeping dependencies up to date

We manage dependencies with [pip-tools](https://github.com/jazzband/pip-tools).

Install pip-tools once (it's a development tool, so it is *not* listed in
`requirements.txt`):

```bash
pip install pip-tools
```

> We keep a **single** requirements file for both runtime and test tooling
> (`pytest`, `requests-mock`). So `pip install -r requirements.txt` gives
> you everything you need to run *and* test the project.

### Add or remove a dependency

1. Edit `requirements.in` (add/remove the top-level package).
2. Re-generate the lock file:

```bash
pip-compile --strip-extras requirements.in     # rewrites requirements.txt
pip install -r requirements.txt                # apply to your venv
```

3. Commit **both** `requirements.in` and `requirements.txt`.

### Upgrade dependencies

```bash
pip-compile --strip-extras -P requests requirements.in   # upgrade just one package
pip-compile --strip-extras -U requirements.in            # upgrade everything
pip install -r requirements.txt                          # apply the upgrades
```

Tip: to match your virtualenv *exactly* to the lock file (installing, upgrading
**and** removing anything that drifted), pip-tools also provides:

```bash
pip-sync requirements.txt
```

## Running the tests

The test tooling is included in the single `requirements.txt`, so if you've done
the Quick start there's nothing extra to install:

```bash
pip install -r requirements.txt   # if not already installed
pytest
```

## Type checking & pre-commit

The code is type-checked with [mypy](https://mypy-lang.org/) (configured in
`pyproject.toml`, scoped to the application code) and linted/formatted with
[ruff](https://docs.astral.sh/ruff/). A handful of further pre-commit hooks run
alongside them:

- **ruff** + **ruff-format** — Python linting and formatting (replaces
  black/flake8/isort).
- **mypy** — static type checking.
- **typos** — catches misspellings in code, comments and docs.
- **actionlint** — validates the GitHub Actions workflow.
- File hygiene — trailing whitespace, end-of-file/line-ending fixes, merge-conflict
  markers, large files, private keys, and shebang/executable consistency.
- Local guards against leftover `icecream`/`pysnooper` debug calls.

**Where should checks run — before committing, or in CI?** The answer is *both*,
and they play different roles:

- **Locally, via pre-commit** — fast feedback the moment you commit, so problems
  never reach the remote. Set it up once:

```bash
pip install pre-commit
pre-commit install          # adds the git hook
pre-commit run --all-files  # run everything now (first run builds tool envs)
```

- **In CI (GitHub Actions)** — the *backstop*. Local hooks can be skipped
  (`git commit -n`) or simply not installed by a contributor, so CI re-runs the
  **same** hooks plus the tests on every push/PR (see `.github/workflows/ci.yml`).
  This follows the advice in *Boost Your Django DX*: run hooks on developer
  machines **and** in CI.

mypy itself isn't in `requirements.txt` — pre-commit runs it (and its type stubs)
in an isolated environment, which is why type-checkers are kept out of the app's
dependencies.

> Repo-root note: `.pre-commit-config.yaml` and `.github/` assume this
> `bindays/` project folder is the git repository root. If it lives inside a
> larger repo, move them to that root and adjust the paths.

## Project layout

```
bindays/
├── bin_check.py              # CLI: `setup` + show upcoming collections (the app)
├── bindays/                  # the package
│   ├── __init__.py
│   ├── models.py             # shared data types (Collection, AddressOption)
│   ├── council.py            # the Council provider interface (no council specifics)
│   ├── cache.py              # council-agnostic caching of parsed results
│   └── councils/             # concrete providers + the registry
│       ├── __init__.py       # SUPPORTED_COUNCILS, get_council (Glasgow is the only one)
│       └── glasgow/          # everything Glasgow-specific lives here
│           ├── __init__.py   # GlasgowCityCouncil provider
│           ├── calendar.py   # fetch + parse the council's HTML calendar
│           └── uprn.py       # address search + UPRN resolution
├── .pre-commit-config.yaml   # local + CI hooks (mypy, hygiene)
├── .github/workflows/ci.yml  # CI: pre-commit + tests on push/PR
├── conftest.py               # pytest setup (blocks real network in tests)
├── pyproject.toml            # Python version, mypy + pytest config
├── tests/                    # unit tests + factory helpers
│   ├── helpers.py
│   ├── test_collections.py
│   ├── test_cache.py
│   ├── test_uprn.py
│   ├── test_council.py
│   └── test_report.py
├── config.json               # created by `setup` (your saved UPRN)
├── cache.json                # created on first lookup (cached collections)
├── requirements.in           # top-level deps (runtime + tests) you edit by hand
├── requirements.txt          # fully-pinned lock file, generated by pip-compile
└── README.md
```

The separation is deliberate. Everything that knows about a specific council
lives under `bindays/councils/<council>/`, behind the `Council` interface in
`bindays/council.py`. For Glasgow that's `councils/glasgow/calendar.py` (the HTML
calendar) and `councils/glasgow/uprn.py` (the address search). If GCC changes
their pages, those are the files to fix; to add another council, drop in a new
`councils/<name>/` provider — without touching the CLI or the cache.
