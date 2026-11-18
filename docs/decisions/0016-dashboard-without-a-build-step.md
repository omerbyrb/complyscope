# ADR-0016: A dashboard without a build step, hardened for the browser

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

The dashboard (issue #32) shows the assessment and risk register from the read-only API
(ADR-0015). It runs in a browser on the same laptop, which brings browser-specific risks
that the CLI never had:

- **DNS rebinding.** A malicious web page can make its own domain resolve to `127.0.0.1`
  and then read a local, unauthenticated API through the visitor's browser. Binding to
  localhost does not stop this on its own.
- **Cross-site scripting.** Risk titles, plans and answer notes come from YAML files that
  people edit. If the page inserted them as HTML, a crafted note could run script.
- **Leaking data.** Loading scripts or fonts from a CDN would tell a third party that the
  page was opened, and would stop the dashboard working offline.

A JavaScript framework with a bundler would add a Node toolchain to a Python project for
a page with four panels.

## Decision

- **Plain files, no build.** `index.html`, `dashboard.css` and `dashboard.js` live in
  `src/complyscope/api/static/`, ship inside the wheel and are served by the same FastAPI
  app at `/` and `/static`. Nothing is loaded from another site.
- **Text only.** The script builds the page with `createElement` and `textContent`. A test
  fails if it uses `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` or
  `eval`.
- **Content Security Policy.** Every response except FastAPI's `/docs` and `/redoc` (which
  load Swagger UI from a CDN) carries
  `default-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none';
  frame-ancestors 'none'`, without `unsafe-inline` or `unsafe-eval`, plus
  `X-Frame-Options: DENY`. So even a missed injection could not run inline script.
- **Host check.** When serving locally, requests whose Host header is not `localhost`,
  `127.0.0.1` or `::1` get 400. With `--allow-remote` any host name is accepted, since the
  API is then deliberately reachable from the network.
- **No caching of API data.** `/api/*` responses send `Cache-Control: no-store`, and every
  response sends `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`.
- **Facts from the server.** Scores, levels, what a risk still needs and whether its
  review is overdue all come from the API, so the dashboard holds no methodology of its
  own and cannot disagree with the CLI.

## Consequences

- No Node toolchain, and the dashboard works offline and from an installed wheel.
- Plain DOM code is longer than a framework component, which is acceptable at this size.
  A much larger UI would justify revisiting this.
- The rendering logic has no automated browser tests yet. The safety rules above are
  tested, and the page was checked by hand with fictional data in light and dark mode and
  at phone width.
