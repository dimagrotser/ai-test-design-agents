# Spike: mutmut and pytest in the SUT environment

Ticket 02, 2026-10-06. Answers the open questions of ADR 0005 before any Binding or Mutation Run code exists.

## Setup

- SUT: GitHub repository `dimagrotser/aws-payments-floci` (public), local checkout `event-driven-payments`. Commit `84b889bb0e39b235a5c8448266ec5d3888552997`, branch `main`.
- All commands ran in a throwaway copy made with `git -C <SUT> archive HEAD | tar -x` into a temporary directory. The SUT checkout was not written to: `git status --short` was empty and `HEAD` unchanged before and after.
- Versions: uv 0.11.6, CPython 3.13.13 (SUT environment), pytest 9.1.1, mutmut 3.8.0. This project runs on CPython 3.12.

## Summary

| # | Question | Answer |
|---|---|---|
| 1 | `uv run --project <SUT>` under 3.13 | Works. uv selects 3.13.13 from the SUT `requires-python`. |
| 2 | pytest in the SUT environment | Available (9.1.1, `dev` group). `tests/unit`: 43 tests collected from 33 test functions, 43 passed in 2.2 s. |
| 3 | mutmut on `src/payments/domain` | Works with mutmut 3.8.0 on 3.13, after three configuration fixes (see below). |
| 4 | Time and mutant counts | 123 mutants, about 1.9 s for the whole run. 118 killed, 5 survived, 0 timeouts, 0 without tests. |
| 5 | Limit to chosen functions | Works with a glob on the mutant name. |
| 6 | Side effects of importing `payments.reporter.handler` | No network, no client created, environment unchanged. One side effect: the root logger level changes to INFO. |
| 7 | stdlib-only Binding or dependencies in the runner | **The Binding and the Test Case wire format are stdlib-only, plain JSON on stdin and stdout.** |

## 1. `uv run --project` under Python 3.13

```
$ uv run --project <copy> python --version
Python 3.13.13
```

The first call builds and installs the SUT environment (38 packages) and later calls reuse it.

## 2. pytest in the SUT environment

```
$ uv run --project <copy> pytest --version
pytest 9.1.1
$ uv run --project <copy> pytest tests/unit -q -p no:cacheprovider
43 passed in 2.20s
```

The Baseline Suite is described as 33 tests in `CONTEXT.md`, ADR 0006 and `docs/PLAN.md`. That is the number of test functions. Parametrized tests expand to 43 collected cases:

| File | Functions | Collected |
|---|---|---|
| `test_config.py` | 3 | 3 |
| `test_engine.py` | 3 | 3 |
| `test_fraud.py` | 7 | 8 |
| `test_processor_handler.py` | 9 | 9 |
| `test_reporter.py` | 7 | 9 |
| `test_transaction.py` | 4 | 11 |

## 3. mutmut on `src/payments/domain`

Command, run inside the copy:

```
uv run --with mutmut==3.8.0 mutmut run
```

Configuration that works, appended to the copy's `pyproject.toml`:

```toml
[tool.mutmut]
source_paths = ["src/payments/domain/"]
pytest_add_cli_args_test_selection = ["tests/unit/"]
also_copy = [
    "tests/",
    "src/payments/__init__.py",
    "src/payments/api/",
    "src/payments/db/",
    "src/payments/processor/",
    "src/payments/reporter/",
]
```

Three things had to be fixed on the way:

- `paths_to_mutate` and `tests_dir` are deprecated in 3.8.0 and warn. The replacements are `source_paths` and `pytest_add_cli_args_test_selection`.
- `also_copy` with a single file in a directory that does not exist yet fails: `FileNotFoundError: mutants/tests/conftest.py`. Copying the directory (`tests/`) works.
- mutmut copies only `source_paths` into `mutants/`. The other `payments` packages must be listed in `also_copy`, otherwise the unit tests fail to import: `ModuleNotFoundError: No module named 'payments.db'`.

mutmut also runs the test suite once unmutated and once with a forced failure before the mutation run. Both checks behaved as expected.

## 4. Time and mutant counts

```
123/123  killed 118  survived 5  timeout 0  no tests 0  suspicious 0
209.68 mutations/second
real 1.83
```

| File | Function | Mutants |
|---|---|---|
| `domain/transaction.py` | `parse_transaction` | 64 |
| `domain/config.py` | `rules_from_env` | 46 |
| `domain/fraud.py` | `evaluate` | 13 |

All 5 survivors are in `parse_transaction`:

| Mutant | Change |
|---|---|
| `_6` | error message uses `type(None).__name__` instead of `type(raw).__name__` |
| `_21` | `amount <= 0` becomes `amount < 0` |
| `_22` | `amount <= 0` becomes `amount <= 1` |
| `_48` | `customer_id=str(raw["customer_id"])` becomes `customer_id=None` |
| `_62` | `customer_id=str(raw["customer_id"])` becomes `customer_id=str(None)` |

Whether any of these is equivalent is not decided here (that is the maintainer's review before Eval Freeze). The two on `amount` are boundary mutants that the existing tests do not kill.

No mutant was generated for a method, such as the `Decision.reason` property in `fraud.py`. All 123 are in module-level functions. Why was not investigated.

The 118 killed out of 123 is the Baseline Suite result on the whole `domain/` directory. It is not the per-Story Kill Rate of ticket 18.

## 5. Limiting mutmut to chosen functions

Mutant names have the form `payments.domain.<module>.x_<function>__mutmut_<n>`. `mutmut run` accepts a glob:

```
$ uv run --with mutmut==3.8.0 mutmut run "payments.domain.fraud.x_evaluate*"
13/123  killed 13
$ mutmut results --all true
13 killed, 110 not checked
```

On a clean `mutants/` directory only the 13 `evaluate` mutants were run and the other 110 stayed "not checked".

## 6. Importing `payments.reporter.handler`

Run with `socket.socket.connect` and `socket.create_connection` replaced by functions that raise, and without AWS or database variables:

```
python 3.13.13
root logger level before/after: 30 20
get_s3 cache after import: CacheInfo(hits=0, misses=0, maxsize=None, currsize=0)
env changed: False
```

The import loads `payments.db.*` (SQLAlchemy, boto3) but makes no network call and creates no client, since `get_s3` is cached and called lazily. The module sets the root logger to INFO at import (`logger.setLevel(logging.INFO)` on the root logger). That is harmless for the Validity Run.

## 7. stdlib-only Binding and wire format

I expected installing this project into the SUT environment to fail, because the package declares `requires-python = "==3.12.*"`. It did not fail:

```
$ uv run --project <copy> --with <copy of this repo> python -c "import atda"
Installed 7 packages
imported .../site-packages/atda/__init__.py
```

`uv run --with` does not enforce `requires-python` of the added package. So the dependency route is technically possible, and the decision rests on other grounds:

- The overlay adds `pyyaml` and this project to the SUT environment, plus duplicate copies of `pydantic` and its dependencies. The SUT environment would no longer be the locked environment of the SUT, and the Mutation Run depends on running the SUT as it is.
- It would run code written and tested for 3.12 on 3.13.
- The SUT pins `pydantic>=2.12`, and its lock happens to hold the same version (2.13.5) as this project. That is a coincidence outside our control.

Decision: **the Binding and the Test Case wire format are stdlib-only, with plain JSON on stdin and stdout, and the pydantic models stay on this project's side of the process boundary.**

## Findings for other tickets

- **Ticket 16 and CI:** the SUT repository is public, so CI can check it out by SHA. Its GitHub name is `aws-payments-floci`, while the docs call it `event-driven-payments`. The Corpus Manifest and the CI checkout need the GitHub name.
- **Ticket 17:** the mutmut configuration above, including the `also_copy` list of sibling packages, is needed in the copy. mutmut 3.8.0 is the version tested.
- **Ticket 18 and docs:** the Baseline Suite is 33 test functions and 43 collected cases. Documents should say which one they mean.
