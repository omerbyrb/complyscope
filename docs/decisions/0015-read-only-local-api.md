# ADR-0015: A read-only API that listens only on localhost by default

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

The dashboard (week 5) needs the assessment, control details and risk register over HTTP.
These describe an organisation's security weaknesses, so exposing them is itself a risk.
Adding authentication, users and sessions would be a large piece of work for a tool that a
small organisation runs on one laptop.

## Decision

- **Read-only.** The API has GET endpoints only: `/api/health`, `/api/assessment`,
  `/api/controls/{id}` and `/api/risks`. Changes to answers or risks happen in the YAML
  files, which keep their history in whatever way the organisation already manages files.
- **Same rules as the CLI.** The API uses the shared `load_assessment`, so it refuses the
  same mismatched or invalid inputs. Errors return 422 with the input at fault
  (`scope`, `framework`, `evidence`, `answers`, `register`).
- **Always current.** Files are re-read on every request, so the API never serves results
  older than the files on disk.
- **Local by default.** `complyscope serve` binds to `127.0.0.1`. Any address that is not
  a loopback address is refused unless `--allow-remote` is passed, with a message that the
  API has no authentication.
- **Optional dependency.** FastAPI and uvicorn come with the `web` extra, so the CLI works
  without them.

## Consequences

- No accounts or tokens to manage, and nothing in the API can change the assessment.
- Sharing the dashboard across a network needs a deliberate flag, and ideally a reverse
  proxy with authentication in front. That is left to the deployer and documented here.
- Re-reading files per request is fine for one organisation's data. A large deployment would
  need caching.
