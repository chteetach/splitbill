# AI usage notes

## Tools used

- **Claude Code (Claude Opus 5.5)**, run in the Claude desktop app. It read the brief PDF,
  set up the toolchain, wrote the backend, tests, Docker Compose file, frontend and the first
  draft of these documents, ran the test suites and linters, and checked the frontend in a
  browser.

_TODO: add any other tools you used, and describe which parts you wrote or rewrote yourself._

## Effective prompts

1. The starting prompt was simply the brief plus "do the task in this file". This worked
   because the brief is precise: the assistant took the business rules, required tests and
   documentation list directly from it.
2. _TODO: add a prompt of your own that worked well, for example asking for a specific test
   or for an explanation of the idempotency design before the interview._

## Incorrect or unsafe AI output, and how it was caught

**1. A concurrency test that never tested concurrency.** The first idempotency test started 10
threads behind a barrier, each posting the same `Idempotency-Key`, and checked that only one
expense was created. It passed. To check that the test could actually fail, the
`ON CONFLICT DO NOTHING` clause was deliberately removed from the insert and the test was run
again. **It still passed.** The requests finished one after another, so every later request
found the first expense in the lookup before the insert, and the race the test claimed to cover
never happened.
*Fix:* the test was rewritten to force the race. The first request is paused after its insert,
before commit. The second request is started, and the test polls `pg_stat_activity` until
PostgreSQL shows it waiting on a lock. Only then is the first request released. The test now
passes on the real code and fails when `ON CONFLICT` is removed. Another deliberate break
(giving the leftover satang to the last members instead of the first) made 7 tests fail, as it
should.

**2. A frontend state bug that showed users a false "not a member" error.** The first version
of the page reset the selected group in a `useEffect` that ran after the user changed. For one
render the new user (dan) was paired with the old group (group 1, which dan is not in), so the
page requested `/groups/1` as dan, received a 404 and showed "Not a member of this group". It
was found by switching users in the browser and confirmed in the API log (four 404s for
`/groups/1`).
*Fix:* the group selection is now reset in the same state update as the user change, and every
fetch ignores responses for a selection the user has already left. After the fix, switching
users produced no 404s.

**3. `.env.example` would not have been committed.** The `create-next-app` template's
`.gitignore` contains `.env*`, which also ignores `.env.example`, a required file. Caught with
`git check-ignore -v frontend/.env.example`, fixed with a `!.env.example` exception.

**4. A test dependency that did not work on this machine.** An embedded PostgreSQL package was
first added so the tests could run without Docker. Its `initdb` failed because the project path
contains Thai characters, which the bundled binaries mis-decoded. It was removed from the
project. The tests instead take an explicit `TEST_DATABASE_URL`, with Docker Compose as the
one-command path.

## Review process before each commit

What was done for every commit in this repository:

- `uv run ruff check .` and `uv run ruff format --check .` (backend), `npm run lint` and
  `npm run typecheck` (frontend) passed.
- `uv run pytest` (60 tests) and `npm test` (26 tests) passed.
- Migrations were applied, rolled back to base and reapplied against a real PostgreSQL 16.
- Key tests were checked against deliberately broken code (see item 1 above) to make sure they
  can fail.
- The frontend was used in a browser: the 100.00 / 3 preview, exact-split unallocated amount,
  0.1 + 0.2 = 0.30, adding, deleting and switching users.

_TODO: describe your own review. For example, reading each diff line by line before
committing, re-deriving the remainder allocation by hand, and being able to explain every file
in the interview._
