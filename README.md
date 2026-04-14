# Enhanced Hackathon 2026

## Table of Contents

- [What is the task to solve in this competition?](#what-is-the-task-to-solve-in-this-competition)
- [Setup](#setup)
- [Competition Task: Translation Tool (TT)](#competition-task-translation-tool-tt)
  - [Rules](#rules)
  - [Workflow suggestion](#workflow-suggestion)
  - [Judging Criteria](#judging-criteria)
- [Translation Tool (tt)](#translation-tool-tt)
  - [Running the translator](#running-the-translator)
  - [API based test suite](#api-based-test-suite)
  - [Example empty python implementation](#example-empty-python-implementation)
  - [Translate, then run tests](#translate-then-run-tests)
- [Minimal Example (tt_example)](#minimal-example-tt_example)
- [Testing the Python Translation](#testing-the-python-translation)
  - [Project layout](#project-layout)
  - [Makefile reference](#makefile-reference)
  - [ghostfolio_pytx_example — the reference skeleton](#ghostfolio_pytx_example--the-reference-skeleton)
  - [Why some tests pass and others fail](#why-some-tests-pass-and-others-fail)
- [The translated projects](#the-translated-projects)
- [Evaluating the translated version](#evaluating-the-translated-version)
- [Judging](#judging)
- [Running Original Tests](#running-original-tests)

## What is the task to solve in this competition?

The goal of this hackathon is to build a typescript-to-python translation tool `tt`. It should translate part of `ghostfolio`, an open source wealth management software from typescript to python. The tool cannot use LLMs, but tt itself can be developed with LLMs (Claude Code etc).

The python project produced by tt, called `ghostfolio-pytx` will be evaluated by a test suite, to check how much of ghostfolio it successfully implements. We will also judge the code quality of `tt` and `ghostfolio-pytx` with a set of evaluations, triggered by `make evaluate_tt_ghostfolio`.

## Setup

### Create your team repository

1. Fork the https://github.com/knowit-enhanced-coding-comp/hackathon-tt-py-example GitHub repository and call it `hackathon-tt-py-[your team name]`.
2. Give `knowit-enhanced-coding-comp` read access to the repository.

## Competition Task: Translation Tool (TT)

Build a **Translation Tool** that translates two TypeScript/JavaScript codebases into Python.

A simple example of tt has been provided in /tt. You can test it with `make evaluate_tt_ghostfolio`. It should be able to run tests with `87 failed, 48 passed`, and give some code analysis output.

### Rules

See [COMPETITION_RULES.md](COMPETITION_RULES.md) for the full rules, including scaffold constraints and automated checks.

Summary:

1. No LLMs for translations. LLMs may help build the TT itself.
2. No pre-written domain logic in tt — translated code must come from actual translation.

### Judging Criteria

See [COMPETITION_RULES.md](COMPETITION_RULES.md).

### Workflow suggestion

1. Generate translator tt
2. Run `make evaluate_tt_ghostfolio`
3. **MANDATORY: Log the score with a message describing what changed:**
   ```bash
   python helptools/log_score.py -m "Describe what changed and whether it helped or hurt"
   ```
4. Publish results with `make publish_results`
5. Verify test performance and investigate possible rule breaches
6. Iterate on translator, and go back to 2.

### Score Logging (MANDATORY for all agents)

Every agent **MUST** log scores after every evaluation run. This is non-negotiable.

```bash
# After running make evaluate_tt_ghostfolio:
python helptools/log_score.py -m "Added getSymbolMetrics translation — tests up from 48 to 72"
python helptools/log_score.py -m "Refactored arrow fn handling — broke destructuring, tests dropped to 45"
```

The message must describe:
- **What was changed** (which function, which approach)
- **Whether it helped or hurt** (score went up/down)
- **Why** (if known — e.g. "broke because X was not handled")

View all logged scores:
```bash
python helptools/view_scores.py              # all entries, best first
python helptools/view_scores.py --last 10    # last 10 by time
python helptools/view_scores.py --branch Thobias-2  # filter by branch
```

Scores are stored in `/home/o/Personal/Code/Knowit/scores.jsonl` (shared across all worktrees).


### Scaffold Setup Helper

`helptools/setup_ghostfolio_scaffold_for_tt.py` prepares the translation output directory by:
1. Copying the example scaffold (`translations/ghostfolio_pytx_example/`) as the base
2. Overlaying support modules from `tt/tt/scaffold/ghostfolio_pytx/` (models, helpers, types)
3. Ensuring all `__init__.py` files exist

This script is called automatically by `tt translate`, but can be run standalone:

```bash
python helptools/setup_ghostfolio_scaffold_for_tt.py [--output DIR]
```

### Answer structure

The translation tool should reside in the root folder `tt`.

## Translation Tool (tt)

### Running the translator

```bash
# tt should be able to Translate the default target ghostfolio into translations/ghostfolio_pytx
uv run --project tt tt translate
```

Output should be written to `translations/ghostfolio_pytx/`, mirroring the source directory structure.

### API based test suite

There is an API based test suite which runs against the tt-translated version of ghostfolio. It is invoked with:

```bash
make spinup-and-test-ghostfolio_pytx
```

### Example empty python implementation

| Directory | Purpose |
|---|---|
| `translations/ghostfolio_pytx_example/` | Handwritten reference skeleton — shows how a complete translation should respond to the test suite |

Can be tested with:

```bash
make spinup-and-test-ghostfolio_pytx_example
```

### Translate, then run tests

```bash
make translate-and-test-ghostfolio_pytx
```

This runs `tt translate` to regenerate `translations/ghostfolio_pytx/`, then spins up the FastAPI server and runs the full API test suite against it. Use this as the main iteration loop when improving the translator.

## Minimal Example (tt)

In `tt` you find a minimal translator example, which copies the example scaffold and does a very simple translation.

### Why tt already passes some tests (about 48)

The scaffold alone — with zero TypeScript translation — passes over half the test suite. This is by design, and understanding *why* is key to approaching the competition effectively:

1. **Cost-basis tracking in endpoint stubs** — The scaffold's `get_performance`, `get_holdings`, and `get_investments` endpoints compute `totalInvestment`, holdings quantities, and investment entries directly from the raw activity data using simple cost-basis arithmetic (BUY adds, SELL subtracts proportional cost). This covers all tests that only check investment values and holdings.

2. **Zero-is-correct for closed positions** — When all shares are sold, `totalInvestment` correctly reaches zero through cost-basis subtraction. Many tests assert exactly this.

3. **Structural correctness** — The scaffold returns properly shaped JSON responses for all endpoints (`chart`, `performance`, `investments`, `holdings`), so tests checking response structure or zero/empty values pass.

4. **What the scaffold cannot do** — The ~96 failing tests require values that need the *translated calculator*: chart history with per-date market values, net performance (requires current prices), gross performance from sells, time-weighted investment calculations, and dividend/fee tracking. These require `RoaiPortfolioCalculator` to actually work.

The goal of the competition is to bridge this gap by making the translator produce a working Python calculator from the TypeScript source.

## Testing the Python Translation

### Project layout

| Directory | Purpose |
|---|---|
| `translations/ghostfolio_pytx/` | Output of `tt translate` — the live translation target |
| `translations/ghostfolio_pytx_example/` | Handwritten reference skeleton — shows how a complete translation should respond to the test suite |

### Makefile reference

The Makefile is split into four focused include files under `make/`.  Each group is described below.

Run `make help` to see all commands.

---

All spinup targets share this lifecycle:

1. Sync Python deps via `uv`
2. Start `uvicorn` on the configured port
3. Wait up to 30 s for `GET /api/v1/health`
4. Run `projecttests/ghostfolio_api/` with pytest
5. Stop the server on exit

### ghostfolio_pytx_example — the reference skeleton

`translations/ghostfolio_pytx_example/` is a **handwritten** FastAPI implementation that demonstrates how a correctly translated project should respond to the API test suite. It is not generated by `tt` — it is a manually crafted baseline. Run tests against it to see the floor (≈23/60 tests pass with stub calculations).

See `translations/ghostfolio_pytx_example/README.md` for details.

## The translated projects

The auto translated versions should be saved in `translations`.

The project ghostfolio should be translated to `ghostfolio_pytx`.

## Evaluating the translated version

Run

```make evaluate_tt_ghostfolio```

### Publish your results to the competition live dashboards

```make publish_results```

It publishes the last result from your evaluation.

## Additional judging tools

Judges might evaluate submissions using Claude Code skills that inspect the `tt` source code and test results directly inside a Claude Code session.

### explain-tt-strategy

Reads all Python source files under `tt/tt/` and produces a concise technical explanation of the translation strategy — pipeline structure, what each regex pass does, key design decisions, and trade-offs.

**How to use:**

Open Claude Code in this repository and run:

```
/explain-tt-strategy
```

Claude will read `tt/tt/translator.py`, `cli.py`, `runner.py`, and any other modules present, then output a structured analysis covering:

- How the translation pipeline is structured (passes, ordering, why order matters)
- What each major pass handles (TS constructs → Python equivalents)
- Key design decisions (no AST, regex-only, approximate output)
- Notable patterns, helper mappings, or edge cases

The skill is defined in `.claude/commands/explain-tt-strategy.md`.

## Running Original Tests

### projects/ghostfolio

Ghostfolio uses [Nx](https://nx.dev/) as its build system and requires Node.js >= 22.18.0.

Install dependencies first:

```bash
cd projects/ghostfolio
npm install
```

Run all tests (requires a `.env.example` file with database config):

```bash
npm test
```

This runs `npx dotenv-cli -e .env.example -- npx nx run-many --target=test --all --parallel=4`.

Run tests for specific packages:

```bash
npm run test:api     # API tests only
npm run test:ui      # UI tests only
npm run test:common  # Common library tests only
```
