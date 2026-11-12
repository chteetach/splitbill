# SplitBill

Records costs shared by members of a group and calculates each member's net balance, exact to
the satang.

- `backend/`: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Python 3.12
- `frontend/`: Next.js 15 (App Router), TypeScript, Tailwind CSS

## Quick start (Docker)

```bash
cp .env.example .env              # optional: change the placeholder credentials
docker compose up --build         # PostgreSQL + API on http://localhost:8000 (migrations run on start)
```

```bash
cd frontend
cp .env.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm ci
npm run dev                       # http://localhost:3000
```

Interactive API docs: <http://localhost:8000/docs>.

## Running the tests

Backend (one command, uses a separate `splitbill_test` database that the suite wipes):

```bash
docker compose run --rm backend-tests
```

Or without Docker, against any PostgreSQL 16 you have:

```bash
cd backend
uv sync
export TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/splitbill_test
uv run pytest
```

Frontend (money helpers and error messages):

```bash
cd frontend && npm test
```

Lint and format: `uv run ruff check . && uv run ruff format --check .` in `backend/`;
`npm run lint && npm run typecheck` in `frontend/`.

## Running the backend without Docker

```bash
cd backend
cp .env.example .env              # point DATABASE_URL at your PostgreSQL
uv sync
uv run alembic upgrade head       # schema + seed users and groups
uv run uvicorn app.main:app --reload
```

## API

All requests identify the caller with an `X-User` header (`alice`, `bob`, `carol`, `dan`).
Amounts are strings with at most two decimals, for example `"1000.00"`.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/users` | Seed users, for the frontend's user picker (no `X-User` needed) |
| GET | `/groups` | Groups of the caller |
| GET | `/groups/{id}` | Group and its members |
| POST | `/groups/{id}/expenses` | `201` on create, `200` + `Idempotent-Replayed: true` on replay |
| GET | `/groups/{id}/expenses` | Newest first, deleted expenses excluded |
| DELETE | `/groups/{id}/expenses/{expense_id}` | Payer only, soft delete, `204` |
| GET | `/groups/{id}/balances` | Positive balance means the member is owed money |
| GET | `/groups/{id}/settle-up` | Suggested payments (extension) |
| POST/GET | `/groups/{id}/payments` | Record and list repayments (extension) |

Errors always look like this:

```json
{ "error": { "code": "shares_mismatch", "message": "The shares add up to 999.99 but the amount is 1000.00", "details": { "amount": "1000.00", "shares_total": "999.99" } } }
```

| Status | Codes |
| --- | --- |
| 401 | `unauthenticated` (no `X-User`), `unknown_user` |
| 403 | `not_payer` |
| 404 | `group_not_found`, `expense_not_found`, `not_found` |
| 405 | `method_not_allowed` (for example `PUT`/`PATCH` on an expense) |
| 409 | `idempotency_key_reused` |
| 422 | `validation_error`, `shares_mismatch`, `not_group_member`, `duplicate_members`, `same_user` |

## Design decisions

**404 rather than 403 for groups you are not in.** A request from alice for group 2 gets the
same `404 group_not_found` as a request for a group that does not exist. Answering 403 would
confirm that group 2 exists, which leaks information to someone who has no business knowing,
and group ids are sequential so they are easy to probe. Inside a group the caller does belong
to, the existence of an expense is not secret, so deleting someone else's expense is an honest
`403 not_payer`.

**Money is never a float.** The API accepts amounts only as JSON strings and rejects numbers,
because a JSON number may already have been rounded by the client's parser. Strings are
validated with a regex (no signs, exponents, `NaN` or spaces), must have at most two decimal
places, must be greater than zero and must fit `NUMERIC(12,2)`. They become `Decimal` in Python
and `NUMERIC(12,2)` in PostgreSQL, with `CHECK (amount > 0)` as a second line of defence.
Responses always serialise amounts as two-decimal strings and never as `-0.00`.

**Remaining satang.** Equal splits work in integer satang: `divmod(total_satang, n)` gives the
base share and the remainder, and the remainder goes one satang at a time to the first members
in the order the request listed them. 1000.00 split among `[alice, bob, carol]` is 333.34,
333.33, 333.33; listing `[carol, bob, alice]` gives carol the extra satang. Each share's
`position` is stored so the order survives. Because every expense's shares sum exactly to its
amount, balances (paid - owed) always sum to 0.00; the service also asserts this and fails
loudly rather than returning inconsistent numbers.

**Exact splits** must sum to the amount to the satang or the request fails with
`422 shares_mismatch`, which names both totals. Each share must be a positive amount with at
most two decimals; members who owe nothing are simply left out.

**Idempotency.** `expenses` has `UNIQUE (group_id, idempotency_key)`. Creating an expense runs
`INSERT ... ON CONFLICT DO NOTHING RETURNING id`. If two requests with the same key race, the
second one's insert waits on the unique index until the first commits, then inserts nothing;
the service then reads and returns the first expense. A cheap lookup before the insert handles
the common case of a plain retry. A SHA-256 fingerprint of the caller and the normalised
request is stored with the key, so reusing a key for a *different* request returns
`409 idempotency_key_reused` instead of silently returning an unrelated expense. `"1000"` and
`"1000.00"` normalise to the same fingerprint. Requests that fail validation never store the
key, so the client can fix the problem and retry with the same key. The key is optional; without
it there is no deduplication.

**Immutability and soft delete.** There is no update endpoint (`PUT`/`PATCH` return 405).
Deleting sets `deleted_at`; deleted expenses are excluded from listings and balances but stay
in the table for auditing. Deleting an already-deleted expense returns 404.

**Who can record and delete.** Any member can record an expense paid by any member (someone
often enters the bill for whoever paid). Only the payer can delete it, as the brief requires,
even if someone else recorded it.

**Layers.** `routers/` handle HTTP only, `services.py` holds the business rules,
`repositories.py` holds queries, `schemas.py` validates request shape and format, and
`money.py` is pure functions with no I/O. `deps.py` resolves the caller and enforces group
membership once for every group route.

**Tests run against real PostgreSQL**, not SQLite, because the behaviour under test
(`NUMERIC`, `ON CONFLICT`, lock waits) is PostgreSQL behaviour. The suite builds the schema
with the real Alembic migrations, so the seed data is exactly what production gets. The
concurrency test forces a genuine race: the first request is paused after its insert and
before its commit, and the test waits until PostgreSQL reports the second request blocked on a
lock before letting the first one finish.

**Frontend money.** The page holds every amount as an integer number of satang (THB x 100),
parsed from the input string without ever going through a float. Adding 0.1 and 0.2 is
10 + 20 = 30 satang, shown as `0.30`. The equal-split preview uses the same remainder rule as
the backend, so 100.00 / 3 shows 33.34, 33.33, 33.33 before submitting. Thai-style formatting
(`1,000.00`) is done by inserting separators into the integer string. The maximum amount,
999,999,999,999 satang, is far below `Number.MAX_SAFE_INTEGER`, so ordinary numbers stay
exact. These rules are unit-tested in `frontend/src/lib/money.test.ts`.

**Frontend idempotency.** The form generates an `Idempotency-Key` the first time it submits and
keeps it until the request succeeds or the form is edited, so a retry after a network error
cannot create a duplicate.

**Settle-up** (extension) greedily pairs the largest debtor with the largest creditor. Each
step settles at least one member, so it never needs more than n - 1 payments. The true minimum
is NP-hard in general (it requires finding the most zero-sum subgroups); greedy is optimal for
the common cases and the groups here are small.

## Assumptions

- Users and groups are fixed seed data; there are no endpoints to create them.
- `paid_by` and every split member must be members of the group; a member may appear in a
  split only once.
- An equal split may give a member 0.00 (for example 0.02 among three people); exact shares
  must each be greater than zero.
- Expenses are listed by creation time (newest first), with the id as tie-breaker.
- Repayments are always between two different members of the group and cannot be deleted.
- Amounts are in THB only.

## Known limitations and next steps

- No real authentication: `X-User` is trusted. Next step: replace it with a session or token
  and derive the user from that.
- Repayments have no idempotency key and cannot be undone; they should get the same treatment
  as expenses.
- No pagination on expense and payment lists.
- Settle-up is greedy rather than provably minimal.
- The frontend has unit tests for its money and error logic but no component or end-to-end
  tests. A Playwright test of the add-expense flow would be the next addition.
- Membership is static; a member leaving a group with a non-zero balance is not modelled.
- The Docker Compose setup was written but not run on the development machine, which had no
  Docker. The tests were run against a local PostgreSQL 16.2 instead.

## Time spent

About 2 hours in total, in two sittings:

- About 45 minutes building the backend, tests, frontend and first drafts of the docs with an
  AI assistant (see `AI_NOTES.md`).
- About 1 hour running the app locally, testing it by hand (checking shares, leftover satang
  and balances with a calculator), fixing the problems found and finishing the documentation.
