# FRIIS backend runtime

The API uses Auth0 access tokens and a SQLAlchemy-backed service. Start from this
directory so the local SQLite URL and `.env` file resolve predictably.

1. Copy `.env.example` to `.env`.
2. Set `FRIIS_AUTH0_DOMAIN` to the Auth0 tenant or custom domain, without a path.
3. Set `FRIIS_AUTH0_API_AUDIENCE` to the exact Identifier configured for the Auth0
   API. In the Auth0 API settings, enable RBAC and **Add Permissions in the
   Access Token** if permission claims are also used by other consumers.
4. Configure the Auth0 Post-Login Action below, add it to the Login flow, and
   assign roles in Auth0. The supplied guide's `user` and `admin` roles are
   supported; the API also recognizes the least-privilege roles `analyst`,
   `risk_manager`, `compliance_reviewer`, and `operator`.
5. Configure the database. For Neon, set `DATABASE_URL_POOLED` to the pooled
   connection string copied from the Neon dashboard; alternatively set
   `FRIIS_DATABASE_URL` or `DATABASE_URL`. URL priority is
   `FRIIS_DATABASE_URL`, then `DATABASE_URL_POOLED`, then `DATABASE_URL`;
   legacy `DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`/`DB_NAME` settings are
   used only when no URL is configured. Keep the connection string in the
   git-ignored `.env` and retain Neon’s `sslmode=require` query parameter.
   Ensure the database has the pgvector server extension installed and
   available (`CREATE EXTENSION vector;`). `FRIIS_AUTO_CREATE_SCHEMA=true` creates missing tables and the
   pgvector index; it is not a migration mechanism for an existing schema.
   Production deployments should run reviewed migrations and set it to `false`.
6. To process document ingestions, set `FRIIS_INGESTION_WORKER_ENABLED=true`.
   The PDFs are read from the repository's `Documents/` directory by default;
   set `FRIIS_DOCUMENTS_ROOT` to override that location. The app registers the
   seven approved project PDFs at startup and processes
   queued `documents` ingestion runs using the configured Azure OpenAI
   embedding deployment. The current schema requires 1536-dimensional vectors.
   PDF text and extracted table content are embedded; pages containing images
   or dense vector graphics are rendered for captions by
   `FRIIS_VISION_DEPLOYMENT` (defaulting to `AZURE_OPENAI_LLM_DEPLOYMENT`). Use
   a vision-capable deployment. Text, table data, and rendered visual pages are
   sent to the configured Azure endpoint; verify organizational data-handling
   approval before enabling the worker.
7. To execute queued analyst queries, set `FRIIS_QUERY_WORKER_ENABLED=true`.
   This also requires `AZURE_OPENAI_LLM_DEPLOYMENT` to identify a deployed chat
   model. Approved document passages are retrieved using both pgvector cosine
   similarity and BM25 keyword search, then merged with reciprocal-rank fusion
   before evidence-constrained synthesis. The synthesis agent calls the
   configured Azure deployment asynchronously with LangChain's
   `AzureChatOpenAI.ainvoke`, requests JSON output, and validates returned
   citations against the retrieved evidence. Query text and retrieved evidence
   are sent to the configured Azure OpenAI endpoint. Optionally set
   `AZURE_OPENAI_JUDGE_DEPLOYMENT` to a separate, strong chat deployment (for
   example, GPT-4.1 or GPT-4o) that supports JSON output; the live and offline
   judge calls use it, falling back to `AZURE_OPENAI_LLM_DEPLOYMENT` when unset.
   The versioned evaluator prompts score faithfulness, correctness, answer
   relevance, usefulness, and context precision. Risk-classification accuracy
   is an exact comparison with the golden label, not a judge self-assessment.
   The Supervisor runs on
   LangGraph's `StateGraph`, using typed request state, parallel specialist
   fan-out, a dependent risk-manager step, and conditional retry/escalation
   edges. It preserves deterministic intent routing, citation allowlisting, one
   bounded synthesis correction attempt, and a persisted human
   escalation when evidence is insufficient, a mandatory review trigger applies,
   or the user explicitly requests human assistance. Reviewer escalation details
   transfer the sanitized answer, citations, limitations, and session ID with the
   escalation packet. It never grants access based on model output. Input
   guardrails reject empty or overlong queries. The local PII scanner redacts personal information
   from answers, citations, and escalation details before results are persisted.
   With Presidio's `en_core_web_lg` model installed it uses Guardrails Hub
   `DetectPII`; without that model it uses Presidio's local regex recognizers
   without attempting a download (named-entity recognition such as people and
   locations is then unavailable). If PII scanning is unavailable or fails, the
   worker fails the query rather than persisting unvalidated output.
8. Install the backend dependencies, then run `uvicorn main:app --reload`.

Swagger UI at `/docs` can obtain an Auth0 access token using Authorization Code
with PKCE. Set `FRIIS_AUTH0_SWAGGER_CLIENT_ID` to a public Auth0 SPA application's
client ID; do not set a client secret. Swagger exchanges its one-time authorization
code through the backend's `/auth/token` endpoint, which forwards only the code,
PKCE verifier, and fixed API audience to Auth0. Add
`http://localhost:8000/docs/oauth2-redirect` and the deployed backend's
`/docs/oauth2-redirect` URL to that application's Allowed Callback URLs, and add
the corresponding origins to Allowed Web Origins. In Swagger, select **Authorize**
and sign in through Auth0. The flow requests the configured
`FRIIS_AUTH0_API_AUDIENCE`; the API continues to validate the returned Auth0 token.

## Deploying the API to Vercel

Create a second Vercel project for this repository; keep the frontend project
rooted at the repository root and set this backend project's **Root Directory**
to the directory containing `main.py`, `pyproject.toml`, and `vercel.json`.
Vercel detects the FastAPI app exported by `main.py` and reads the Python version
and dependencies from `pyproject.toml`/`uv.lock` (Python 3.12).

The current dependency set produces a Python function bundle larger than the
standard 500 MB limit. On an eligible project with Fluid Compute and Active CPU
enabled, set the Vercel project environment variable
`VERCEL_SUPPORT_LARGE_FUNCTIONS=1` for the deployment environments, then
redeploy. Vercel's Large Functions beta supports bundles up to 5 GB. The
`functions` configuration excludes local PostgreSQL data and non-runtime test
and evaluation files; `.vercelignore` also keeps local environment files and
development artifacts out of deployments.

Add these environment variables to the Vercel project for each environment:

- `DATABASE_URL_POOLED`: pooled PostgreSQL URL with `sslmode=require` and pgvector installed.
- `FRIIS_AUTH0_DOMAIN` and `FRIIS_AUTH0_API_AUDIENCE`: the Auth0 tenant and API identifier.
- `FRIIS_AUTH0_SWAGGER_CLIENT_ID`: public Auth0 SPA client ID for Swagger's PKCE login.
- `FRIIS_CORS_ALLOW_ORIGINS`: comma-separated exact frontend origins, for example
  `https://project-3-finance-risk-investment-i.vercel.app`.
- `FRIIS_AUTO_CREATE_SCHEMA=false`: apply reviewed database migrations separately.
- `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`: required while the Python function bundle exceeds 500 MB.

After deploying, set `VITE_API_BASE_URL` in the frontend Vercel project to this
backend's HTTPS deployment URL and redeploy the frontend. The backend currently
stores research and ingestion requests in PostgreSQL for separate polling
workers. Vercel Functions are not a durable always-on worker process, so run
the query/ingestion workers as a separate long-running service against the same
database; do not rely on enabling the in-process worker flags in the Vercel
project to continuously drain those queues.

9. The backend also includes a read-only tool-enabled finance agent. When Azure
OpenAI LLM settings are configured, the app exposes `GET /api/v1/agent/ask` to
admins, analysts, risk managers, and compliance reviewers. Because the agent's
tools are not request-scoped, the endpoint also requires an explicit
all-portfolios access claim. Its tools are read-only and do not mutate database
state.

10. FRIIS requires managed prompts from Langfuse (Python SDK 5.x). Set
    `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_ENABLED=true`,
    and optionally set `LANGFUSE_BASE_URL` plus
    `LANGFUSE_TRACING_ENVIRONMENT` in the local `.env`. The local catalog
    contains prompt names and metadata only; it has no prompt text or fallback.
    Missing prompts, unsupported prompt formats, or unavailable Langfuse
    credentials raise an error instead of using a local prompt. Prompts are
    loaded when their workflow modules initialize, so restart the application
    after publishing prompt changes.
    Query processing creates a Langfuse trace with specialist, retrieval,
    embedding, and synthesis observations. The synthesis observation records
    the managed prompt name, version, label, and `prompt_source: "langfuse"`
    without capturing prompt content. Upload and approved-source ingestion
    also create processing observations. Every trace includes flow identifiers,
    selected portfolio scope, step counts, model names, and token usage when
    the provider returns it. User prompts, model
    answers, retrieved excerpts, portfolio records, uploaded filenames, and
    document text are not sent to Langfuse. Keep Langfuse credentials in `.env`
    and verify your organization's observability data-handling approval before
    enabling remote tracing.
    When the root trace is created, a `query.trace.created` log includes the
    durable `query_id` and matching Langfuse `trace_id` to correlate application
    and trace events.
    Completed, clarification, and escalated query results are scored for
    faithfulness, correctness, answer relevance, context precision, usefulness,
    and confidence on a 0-1 scale. A bounded evaluator call uses the PII-redacted
    question, result, and cited excerpts
    with the configured Azure chat deployment. When Langfuse tracing is enabled,
    only numeric scores and the query ID are attached to the trace. Results below
    the handoff thresholds (faithfulness 0.6, relevance 0.5, or confidence 0.4),
    scored results without evidence, and existing escalations are persisted for
    human review before an email notification is attempted. Configure `SMTP_HOST`,
    `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `APPLICATION_EMAIL`, and
    `SUPPORT_EMAIL` to enable notifications. Email contains the query/trace
    identifiers, trigger reason, and scores, but not the question, answer,
    citations, or portfolio data. Evaluation failures do not fail or escalate an
    otherwise completed query; email failures are logged after the query result
    is persisted. The evaluator has a 15-second timeout and runs before the
    worker marks the result terminal.

Application logs are written to stdout and, outside Vercel, appended to
`logger.txt` in this backend directory. Vercel's function filesystem is
read-only, so deployed logs are available through the Vercel function logs. The
admin document-upload endpoint logs request validation,
upload size/type, pipeline start and completion statistics, failures, and
temporary-file cleanup. Ingestion logs include the normalized destination table
(`document_chunks`), ingestion IDs, and chunk counts. Document contents and
credentials are not logged.

The operator-only `POST /api/v1/admin/ingestions` endpoint accepts a multipart
`file` upload (`.pdf`, `.txt`, `.md`, `.markdown`, `.html`, or `.htm`, up to
10 MB), plus optional `chunk_size` and `chunk_overlap` query parameters. It
synchronously loads and splits the file with LangChain, embeds the chunks with
the configured Azure OpenAI embedding deployment, and stores a registered
source, a valid document version, and searchable chunks in `source_documents`,
`document_versions`, and `document_chunks`. Uploaded sources are marked
approved and enabled because this endpoint is restricted to administrators and
operators. Query-worker retrieval searches these same normalized tables. For
PDF uploads it also extracts tables and creates visual-page captions using the
vision deployment described above; upload responses report the number of table
and image nodes. The uploaded PDF bytes are not retained after processing; the
normalized tables retain the extracted chunk text and embeddings.

RAG ingestion follows these operating principles:

1. **Idempotency:** uploaded source identity is derived from the normalized
   filename, version identity from the source plus content SHA-256, and chunk
   IDs from the version, chunking profile, index, and chunk text. Retrying an
   already indexed upload returns its existing chunk IDs without another
   embedding call.
2. **Incrementality:** unchanged versions are skipped. Changed content creates
   a new version; unchanged chunk text reuses its prior embedding. After its
   chunks are committed, prior versions are marked `superseded` so retrieval
   sees the current valid version. A changed chunking profile triggers a
   reindex and records a new profile.
3. **Determinism:** chunk ordering, stable IDs, a named/versioned chunking
   profile, and stable text normalization make retries reproducible. Bump the
   ingestion pipeline version when extraction or chunking behavior changes.
   Embedding provenance records the configured deployment and API version, but
   Azure does not expose an immutable model-build identifier here; keep
   deployments pinned operationally and reindex after retargeting one.
4. **Structure awareness:** splitting favors headings, paragraphs, lines, and
   sentence boundaries; PDF page numbers, table/image content kinds, section
   hints, and chunk offsets are retained with each passage.
5. **Noise reduction:** ingestion removes control characters, zero-width
   artifacts, soft hyphens, non-breaking spaces, repeated page headers and
   footers, page counters, trailing whitespace, and excessive blank lines while
   retaining meaningful line and table structure.
6. **Metadata first:** source key, original filename, file type, content hash,
   version, chunk profile/index, page, section, and pipeline version are stored
   alongside chunks for filtering, citations, and diagnosis.
7. **Access control:** only administrators and operators can upload. Uploads
   are registered as approved internal sources, and retrieval excludes sources
   that are disabled/unapproved or versions that are not valid. The current
   knowledge base is shared across authorized research roles; it does not yet
   support per-user or per-portfolio document visibility.
8. **Observability:** structured events cover stable identity resolution,
   unchanged skips, storage outcomes, and durations/counts. Langfuse spans
   capture load, chunk, embed, and persist stages without document text.
   Every HTTP route also records its route template, method, status, and
   duration. Research-query traces include planner, delegation, phase changes,
   evidence routing, retries, retrieval, synthesis, and terminal status. The
   tool-enabled agent, reviewer updates, and ingestion-run outcomes are covered
   as well. Request bodies, uploaded content, reviewer notes, and evidence text
   are excluded from the shared HTTP trace; query logging continues to use the
   existing PII-sanitized query field.

When enabling the query worker against an existing database with
`FRIIS_AUTO_CREATE_SCHEMA=false`, apply the schema migration for
`query_workflow_events` and `2026_11_10_query_portfolio_scope.sql` before
deployment. `create_schema()` applies additive upgrades only when local
auto-creation is enabled; it does not migrate production schemas.

The local auto-created database is empty. Load the project's standardized
synthetic dataset before using portfolio endpoints; schema creation does not
seed sample data or make that synthetic data representative of live markets.

The Auth0 tenant name, API Identifier, and role assignments are tenant-specific;
they are intentionally not fabricated in the checked-in environment template.
Never put an Auth0 client secret or access token in this backend `.env` file.
This API validates bearer access tokens using the tenant's HTTPS JWKS endpoint;
it does not use a client secret to validate user tokens.

## Auth0 Post-Login Action

The supplied Auth0 guide uses a namespaced roles claim in the access token. This
Action emits that claim and optional portfolio-scope claims from administrator-
controlled `app_metadata`; do not source authorization from user-editable
`user_metadata`.

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const namespace = "https://friis-api";
  const roles = event.authorization?.roles ?? [];

  api.accessToken.setCustomClaim(`${namespace}/roles`, roles);
  api.accessToken.setCustomClaim(
    `${namespace}/portfolio_ids`,
    event.user.app_metadata?.portfolio_ids ?? []
  );
  api.accessToken.setCustomClaim(
    `${namespace}/all_portfolios_access`,
    event.user.app_metadata?.all_portfolios_access === true
  );
};
```

Only set `all_portfolios_access` for accounts explicitly approved for that
scope. The backend maps recognized role strings to its allowlist and rejects
tokens with missing/unsupported roles. A role does not grant portfolio access
by itself; access still requires the explicit portfolio claim or the explicit
all-portfolios claim.

## API service boundaries

`DatabaseAPIService` persists query submissions and ingestion runs as queued
work. The optional document worker loads approved PDFs with LangChain's
`PyPDFLoader`, supplements extracted text with PyMuPDF table extraction and
vision-generated captions for visual pages, splits each content type with
`RecursiveCharacterTextSplitter`, stores versioned chunks and 1536-dimensional
vectors in PostgreSQL/pgvector, and records per-source results. Successful
direct file uploads also register a source and version, persist a terminal
ingestion-run record, and write chunks to the same `document_chunks` table
searched by the query worker. The response includes an `ingestion_id`; the
submitting operator can retrieve its status at
`GET /api/v1/admin/ingestions/{ingestion_id}`. Structured-data ingestion
requests are rejected until a compatible worker and validation path are
implemented. The optional query worker consumes queued queries, writes
redacted workflow events, delegates to document/portfolio/risk specialists,
validates citations, and persists completion or an escalation packet. Leave
`FRIIS_QUERY_WORKER_ENABLED=false` when no approved Azure chat deployment is
configured. Run a single application worker process for each queue; each
process starts its own poller.

The query planner routes portfolio holdings, allocations, record-level risk
metrics, and investment-decision history to the read-only structured-data
analyst. Portfolio-specific questions require a portfolio ID in the request;
the API validates that ID against the caller's authorized scope before queuing
the query. Market-indicator questions can use the global synthetic indicator
records without a portfolio ID. Policy and regulatory questions continue to
use document retrieval, and hybrid questions can use both sources.

The query supervisor executes a bounded Plan–Act–Check workflow as a LangGraph
`StateGraph`. The query's `QueryContext` is passed as runtime context, and
typed graph state carries the plan, phase, specialist results, correction
budget, evidence, and outcome. It records workflow phases and task delegation
in `query_workflow_events`, fans independent leaf specialists out in parallel,
then gives validated child results to the risk manager for cross-checking.
Evidence identity and citation
provenance are checked before synthesis. A failed specialist, including
Document Retrieval, receives up to two retries (three total attempts). An
empty retrieval gets the same bounded retry budget, with a keyword-focused
query on retries and the approved-source filter unchanged. Synthesis may use
one correction attempt when specialist retries were not needed. Unresolved
failures, insufficient evidence, and mandatory review conditions escalate.
Workflow, agent, and synthesis timeouts remain bounded. The planner and data
access rules stay deterministic; model synthesis cannot alter authorization,
request scope, or escalation decisions.

Graph state currently lives for one worker invocation; query status and workflow
events remain durable in FRIIS's database, but LangGraph checkpointer-based
resume after a process interruption is not enabled.

For manually trying evidence-backed queries through the document retriever,
portfolio/market specialist, and LLM synthesis, see
[`llm_rag_agent_queries.md`](./llm_rag_agent_queries.md). The examples avoid
intentional handoff requests and note the data and ingestion prerequisites.

## Golden evaluation dataset

The versioned 50-case evaluation set is in
[`evaluation/golden_dataset_v1.json`](./evaluation/golden_dataset_v1.json). It
contains 15 policy/RAG, 10 portfolio/SQL, 10 hybrid-risk, 10 high-risk decision,
and 5 escalation cases, along with source references, answer rubrics, escalation
expectations, and a deterministic synthetic SQL fixture with expected results.
The runner loads the fixture into an isolated in-memory SQLite database; do not
copy its synthetic rows into a shared or production database. The set is marked
`draft_requires_domain_review`: have policy and risk stakeholders verify the
labels and expected behavior before using it for acceptance claims.

An automated runner is available at
[`evaluation/slo_evaluation.py`](./evaluation/slo_evaluation.py). It submits the
cases serially to the authenticated query API, waits for terminal results, and
uses the configured Azure OpenAI chat deployment as an LLM judge for online
quality scores.
Set `AZURE_OPENAI_JUDGE_DEPLOYMENT` to a separate, strong model for judging;
it falls back to `AZURE_OPENAI_LLM_DEPLOYMENT`. Both use deterministic
generation where supported. The v2 evaluator rubric scores faithfulness,
correctness, answer relevance, usefulness, and context precision. Risk
classification accuracy is an exact comparison with the golden expected label,
not a self-reported judge score.

To run evaluations in Langfuse, upload the labeled dataset with
`python -m evaluation.dataset_evaluation`, then run your Langfuse evaluator
against that versioned dataset. Supply the case's `answer_rubric`,
`required_evidence`, `expected_result` (when present), and
`expected_risk_class` alongside the generated status, answer, and cited
excerpts. The prompt contracts are versioned in
[`prompts/catalog.py`](./prompts/catalog.py); keep the expected risk label as a
comparison target, not an instruction to copy.

To run it:

1. Review the golden labels with domain stakeholders. The runner seeds an
   isolated in-memory SQLite database from the fixture; it does not require
   loading fixture rows into another database.
2. Start the API with the query worker enabled and its approved Azure
   deployments configured. Use an evaluation bearer token with the roles and
   portfolio scope needed for the fixture cases.
3. From this `backend` directory, set `FRIIS_EVALUATION_TOKEN` in the process
   environment, then run:

   ```sh
   python -m evaluation.slo_evaluation --api-url http://127.0.0.1:8000
   ```

The runner evaluates deterministic planner routes, structured-agent evidence
against the fixture in an isolated in-memory SQLite database, cross-tenant
authorization, and the implemented input/output guardrails locally. RBAC
checks cover authorized and cross-tenant portfolio access, query submission,
query ownership, and structured authorization-denial audit events. Guardrails
use the versioned [adversarial dataset](./evaluation/guardrail_attack_dataset_v1.json)
for empty/oversized input, benign input, and output PII redaction. Its
prompt-injection case is recorded as unverified because safe handling requires
an end-to-end model/API assertion; it is not included in the deterministic
pass rate. Each offline SQL case includes its normalized `actual_result` and
`expected_result`; the comparison rejects missing, unexpected, or mismatched
rows and values. These results are written only to the local evaluation
report, not exposed by the production API. The runner does not connect to or
mutate the configured application database for offline checks. The runner reads Azure
endpoint, API key, API version, and chat deployment settings from the process
environment or this backend's git-ignored `.env`. The judge deployment is
selected by `AZURE_OPENAI_JUDGE_DEPLOYMENT` when set; otherwise the runner
reuses `AZURE_OPENAI_LLM_DEPLOYMENT`.
`FRIIS_EVALUATION_API_URL` may be used instead of `--api-url`. An optional
`--report path.json` writes a report without storing answer text. The runner
returns a non-zero exit status if any measured SLO misses its target or a
configured Langfuse publication fails. If `FRIIS_EVALUATION_TOKEN` is absent,
the 50 online query/judge cases are skipped and their scores remain unmeasured.
When Langfuse credentials are configured, measured deterministic SLOs—including
latency, retrieval recall, task success, SQL correctness, routing, risk
classification, attribution, RBAC, guardrails, critical misclassification, and
escalation recall—are published with sample counts and target status on an
aggregate evaluation trace. Metrics without observations are omitted rather
than published as zero. Online per-query deterministic and judge scores link
to the research traces by query UUID. Use `--skip-langfuse` to generate a
local-only report.

The report includes the documented quality, latency, retrieval, SQL, routing,
escalation, attribution, and risk-classification SLOs. Quality score targets
are reported as the fraction of cases meeting the per-case score threshold;
latency uses p95 end-to-end API time. Routing is computed using the same
deterministic `QueryPlanner` used by the supervisor because the public query
response does not expose selected agents. Critical misclassification and
mandatory escalation metrics use the golden labels as denominators; an
unevaluated case in a partial run counts as a miss; if no online cases ran,
the metric stays unmeasured and lists missing case IDs. It also reports
critical/non-critical dataset coverage. RBAC and
deterministic guardrail results are measured by their offline suites. A judge's
risk labels and confidence are evaluation signals, not independent ground
truth. Accuracy counts labeled route, risk, and SQL predictions; retrieval
recall matches required source sections and structured-record references
against the citations returned by the API, not unexposed retriever candidates.
Task success requires the expected terminal status, correct route and risk
label, complete required-evidence retrieval, and an exact SQL result for SQL
cases. SQL correctness is checked by running the structured analyst against an
isolated SQLite fixture and comparing normalized rows and values; it does not
measure SQL results returned through the public query API or a future N2SQL
executor unless that execution path is explicitly wired into the offline
evaluator.
# finance-risk-investment-intelligence-system-fastapi-service
