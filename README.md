# Fieldwork · Autonomous Research Agent

A local-first research workspace that turns a question into an inspectable evidence brief. Built with Python 3.11+ and browser-native HTML, CSS, and JavaScript. No runtime package installation or build step is required.

## Start

```sh
cd /workspace/Autonomous-Research-Agent
python app.py
```

Open the application on port **8000** in your local browser. It binds to `127.0.0.1` by default. Stop with Ctrl+C. `HOST` and `PORT` override the bind address; this is a **single-user application without authentication**, so do not expose it publicly without an authenticated reverse proxy.

Click **Explore a sample** to inspect an illustrative project, or **New research** to run your own question. Samples are explicitly labeled and never presented as retrieved publications.

## Research workflow

1. Enter a question, optional focus, and standard or in-depth research scope.
2. Enable live discovery (Wikipedia introductory text and Crossref scholarly abstracts), supply a public HTML/text URL, or paste a source excerpt. Disable discovery to use only your evidence.
3. The background worker records a research plan and collects sources.
4. With an OpenAI key, it synthesizes findings and identifies explicit conflicting claims using source quotations. Without a key, it selects relevant **verbatim passages** into an extractive brief; it does not claim to interpret evidence or detect contradictions.
5. Inspect every finding's evidence, source attribution, retrieval status, and limitations. Citation buttons open the corresponding source. The evidence table keeps claims and passages side by side.
6. Export Markdown containing findings, quotations, citation numbers, conflicts, limitations, and a source bibliography.

Projects and source excerpts persist in SQLite at `.data/research.db`. Use `RESEARCH_DB` to choose another location. Running jobs interrupted by a process restart become retryable failures. Re-run a project from its workspace; discovery results are deduplicated by URL against existing sources.

## Optional AI synthesis

Set `OPENAI_API_KEY` securely in the server's environment, then restart. Never commit a key or put one in browser code. `OPENAI_MODEL` defaults to `gpt-4.1-mini`. The Settings screen reports whether the server has a key; it never displays its value.

AI mode sends the question, focus, and available source excerpts to OpenAI's Chat Completions API. The model must return structured claims with exact quotations. The server discards citations to unknown sources and quotations absent from the source text. Unsupported claims are omitted. Conflict entries require matching quotations from at least two sources. If model invocation or validation fails, the app visibly falls back to extractive mode.

**Exact quotation matching establishes text provenance, not entailment, scientific quality, consensus, or factual truth.** Users must review sources and assess whether each passage supports the full claim. No system here independently fact-checks a publication. Abstracts and introductions are not substitutes for full-text review.

## Network requirements

- `en.wikipedia.org`: reference discovery
- `api.crossref.org`: scholarly discovery
- `api.openai.com`: optional model synthesis
- Public source hostnames provided by the user: optional URL retrieval

Keep TLS verification and the environment's proxy/CA settings enabled. Discovery failures are recorded in the project; uploaded evidence can still produce a brief. When every provider fails and no excerpts exist, the project displays an actionable failure instead of fabricating results. In the current cloud instance, the discovery destinations were denied by the outbound proxy; add them in environment network settings to enable live discovery. AI execution requires both network access and a configured key.

Source retrieval accepts HTTP(S) HTML/text only, checks public addresses and redirect destinations, restricts ports, limits response sizes, and applies timeouts. PDFs and other binaries must be supplied as pasted excerpts. Research/source content is escaped before rendering; model source text is treated as untrusted data. Cross-origin writes are rejected. This is not a multi-tenant or hardened public web service.

## Validate

```sh
python -m unittest discover -s tests -v
node --check static/app.js
```

The standard-library tests exercise persistence, the full HTTP create/run/export workflow, valid and invented citation handling, conflict provenance, failure recovery, private URL rejection, sample labeling, and cross-origin/traversal rejection. Tests use a temporary database and mock external services; they do not require paid requests or fabricate successful live integration checks.

## Structure

```text
app.py               HTTP API, SQLite storage, discovery, research worker,
                     optional LLM synthesis, evidence checks, Markdown export
static/index.html    Accessible application shell and research dialog
static/app.js        Workspace navigation, research UI, polling, citations
static/style.css     Responsive workspace design and motion preferences
tests/test_app.py    Unit and HTTP integration tests
```

### API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/config` | Non-secret model availability |
| `GET /api/projects` | List saved projects |
| `POST /api/projects` | Create a project with optional sources |
| `GET /api/projects/:id` | Read project, sources, findings, and status |
| `POST /api/projects/:id/run` | Start/retry background research |
| `GET /api/projects/:id/export` | Export Markdown report |
| `POST /api/sample` | Create an explicitly illustrative sample |

Creation accepts `question`, `focus`, `depth` (`standard` or `deep`), `discovery` (boolean), and `sources` (`title`, `url`, `text`). Source text must be at least 50 characters; if URL is set without text, the server retrieves the page. Pasted excerpts remain labeled user-provided, even when associated with a URL.

## Current boundaries

Search is relevance based, not an exhaustive systematic review. Full text, paywalls, OCR, embeddings, collaboration, scheduled research, and authentication are not implemented. Reports organize evidence and make its provenance inspectable; human judgment remains necessary.

### Optional browser smoke test

A browser check in `tests/browser.cjs` starts an isolated server and temporary database, exercises desktop/mobile workflows, and writes screenshots and an export to `/tmp`. It requires Playwright and Chromium only as development tools:

```sh
npm install --prefix /tmp/fieldwork-browser --cache /tmp/fieldwork-npm-cache playwright
NODE_PATH=/tmp/fieldwork-browser/node_modules CHROMIUM_PATH=/usr/bin/chromium node tests/browser.cjs
```

If using Playwright's downloaded Chromium, omit `CHROMIUM_PATH` after running its browser installation command. `TEST_PORT` overrides the smoke test's default port 8765. Browser validation passed in this cloud instance using its existing `/usr/bin/chromium`; no runtime Node dependencies are required by the app.
