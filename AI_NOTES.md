# AI usage notes

## Tools used

- **Claude Code (Claude Opus 5.5)**, run in the Claude desktop app. It read the brief PDF,
  set up the toolchain, wrote the backend, tests, Docker Compose file, frontend and the first
  draft of these documents, ran the test suites and linters, and checked the frontend in a
  browser.

- **VS Code**, used to open the project and run the database, API and frontend together
  through VS Code tasks (`Tasks: Run Task`).

What I did myself:

- Ran the full stack locally in VS Code and tested the page by hand in the browser.
- Found two problems that the generated code and its automated checks had missed: the VS Code
  task failed because PowerShell blocks `npm.ps1` on this machine, and the page showed
  "Could not reach the server" even though the API was running (item 5 below). I reported both
  and checked the fixes.
- Read through the generated documentation and decided what to submit.

## Effective prompts

1. The starting prompt was simply the brief plus "do the task in this file". This worked
   because the brief is precise: the assistant took the business rules, required tests and
   documentation list directly from it.
2. When the page failed, I pasted the exact error text the page showed, with nothing else:
   "Could not reach the server. Check that the API is running and try again." This worked
   because the message was specific. Instead of guessing, the assistant checked each part in
   turn: the database and the API were running and answered requests, so it tested CORS and
   found that the API only accepted requests from `http://localhost:3000`, not from
   `http://127.0.0.1:3000`. Pasting real error output, rather than describing it, led straight
   to the cause.

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

**5. A CORS setting too narrow for real use.** The generated config allowed browser requests
only from `http://localhost:3000`. Every automated check passed, because the tests call the API
directly and the assistant's own browser check happened to use `localhost`. When I ran the
app myself, the page showed "Could not reach the server" while the API was up. Sending a
request with an `Origin: http://127.0.0.1:3000` header confirmed that the API did not return
an `Access-Control-Allow-Origin` header for that origin, so the browser blocked the response.
*Fix:* the default and `.env.example` now allow both `localhost` and `127.0.0.1`, verified by
repeating the same request for both origins.

## Review process before each commit

Automated checks run by the assistant while building each part. They were run on each part
before it was committed, but not separately on every intermediate commit; for example, commit
`40f6137` imports routers that only arrive in the next commit.

- `uv run ruff check .` and `uv run ruff format --check .` (backend), `npm run lint` and
  `npm run typecheck` (frontend) passed.
- `uv run pytest` (60 tests) and `npm test` (26 tests) passed.
- Migrations were applied, rolled back to base and reapplied against a real PostgreSQL 16.
- Key tests were checked against deliberately broken code (see item 1 above) to make sure they
  can fail.
- The frontend was used in a browser: the 100.00 / 3 preview, exact-split unallocated amount,
  0.1 + 0.2 = 0.30, adding, deleting and switching users.

My own review was hands-on rather than line-by-line:

- I ran the app and used it as a user would: picking users and groups, adding expenses with
  equal and exact splits, and checking the balances.
- For each expense I worked out the expected numbers with a calculator and compared them with
  the page: that every share was right, that the leftover satang went to the first members
  listed, that the shares added up to the total and that the balances summed to 0.00.
- Anything that did not behave as expected I reported with the exact error text and re-tested
  after the fix (items 5 and the `npm.ps1` problem above).
