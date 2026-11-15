FRIIS stores approved project documents and Knowledge Operations uploads in the same normalized document tables. Both paths create searchable rows in `document_chunks` linked to `document_versions` and `source_documents`.

### Portfolio and market data

| Table | Purpose |
|---|---|
| `portfolios` | Portfolio names, managers, risk categories, values, and benchmarks. |
| `portfolio_holdings` | Assets and allocations belonging to portfolios. |
| `asset_risk_logs` | Risk assessments, scores, levels, descriptions, and escalation flags for assets. |
| `market_indicators` | Dated market measurements and their trend direction. |
| `investment_decisions` | Portfolio investment decisions, reasons, approval status, and links to risk assessments. |

### Queries and workflow

| Table | Purpose |
|---|---|
| `query_requests` | Submitted questions and their processing status, answer, citations, limitations, or failure details. |
| `conversation_sessions` | Short-lived session continuity, storing users’ explicit questions. |
| `query_workflow_events` | Trace events from the multi-agent workflow, such as planning, delegation, and agent results. |
| `escalations` | Requests that need human review, with the reason, evidence, attempted steps, and review outcome. |

### Approved-source document pipeline

| Table | Purpose |
|---|---|
| `source_documents` | Registry of approved project sources and operator-uploaded documents, including title, type, URI, approval, and enabled status. |
| `document_versions` | Version, content hash, storage URI, and validation metadata for each source document. |
| `ingestion_runs` | Overall records for document ingestion runs, including status and timing. |
| `ingestion_run_items` | Per-document-version status and counts within an ingestion run. |
| `document_chunks` | Searchable passages and embeddings used by the query worker for evidence retrieval. |

Knowledge Operations uploads are registered as approved sources and their extracted chunk text and embeddings are written to `document_chunks`. The temporary uploaded file is removed after processing; FRIIS retains the normalized source/version metadata and chunks, not the original file bytes.
The background ingestion worker uses `ingestion_runs` and `ingestion_run_items` for queued project-source jobs. Direct Knowledge Operations uploads are synchronous and do not create those run records. Portfolio, market, query, session, workflow-event, and escalation tables are used by their respective API and research flows above.

## Sample query workflow map

For portfolio queries, select an accessible portfolio in the **Context** dropdown. Typing an ID into the question does not set `portfolio_id`. Document retrieval searches approved, enabled, valid rows in `document_chunks`; uploaded PDFs must be reuploaded through the normalized ingestion flow to be searchable. Outcomes that depend on retrieved records are data-dependent.

| # | Sample query | Expected flow | Expected outcome |
|---:|---|---|---|
| 1 | What does the risk management policy say about concentration limits? | Document Retrieval | Cited policy answer if matching evidence exists. |
| 2 | Summarize the investment strategy’s asset allocation guidance. | Clarification as written: “allocation” requires portfolio context. | Select a portfolio, or rephrase as “What does the strategy say about diversification?” for document-only retrieval. |
| 3 | What compliance controls are described in the approved documents? | Document Retrieval | Cited compliance answer if evidence exists. |
| 4 | What does the policy say about escalation when an exposure limit is breached? | Clarification without portfolio context: “exposure” requires context. | Select a portfolio; then hybrid policy and portfolio analysis. |
| 5 | Which documents describe market risk? | Portfolio/Market + Document Retrieval | Hybrid research with citations if evidence exists. |
| 6 | What evidence supports the policy’s guidance on diversification? | Document Retrieval | Cited answer if evidence exists; otherwise likely insufficient-evidence escalation. |
| 7 | What are the key requirements in the Basel guidance? | Document Retrieval | Cited Basel-related answer if evidence exists. |
| 8 | What limitations should I know about when using the risk policy? | Document Retrieval | Cited policy answer with limitations. |
| 9 | Compare the investment strategy guidance with the risk management policy. | Document Retrieval | Cited comparison if both sources are available. |
| 10 | Find approved document passages about regional exposure. | Clarification without portfolio context: “exposure” requires context. | Select a portfolio, or rephrase to ask about regional guidance in documents. |
| 11 | Summarize portfolio [ID] and its holdings. | Portfolio/Market Analyst | Portfolio and holdings summary with citations; select [ID] in Context. |
| 12 | What is the largest holding in portfolio [ID]? | Portfolio/Market Analyst | Largest available holding; select [ID] in Context. |
| 13 | Which sectors are represented in portfolio [ID]? | Portfolio/Market Analyst | Sector breakdown from holdings; select [ID] in Context. |
| 14 | What are the allocation percentages for portfolio [ID]? | Portfolio/Market Analyst | Available allocation data; select [ID] in Context. |
| 15 | Which holdings in portfolio [ID] have risk assessments? | Portfolio/Market + Document Retrieval + Risk Policy | Available assessments and policy evidence; select [ID] in Context. |
| 16 | What are the latest risk assessments for the assets in portfolio [ID]? | Portfolio/Market + Document Retrieval + Risk Policy | Latest available assessment records with citations; select [ID] in Context. |
| 17 | Are any risk assessments for portfolio [ID] flagged for escalation? | Portfolio/Market + Document Retrieval + Risk Policy | Flagged records lead to human review. The original wording “holdings flagged for escalation” may not trigger risk-record retrieval; include “risk assessments.” |
| 18 | Which holdings in portfolio [ID] have the highest risk scores? | Portfolio/Market + Document Retrieval + Risk Policy | Risk scores and supporting evidence; select [ID] in Context. |
| 19 | What investment decisions have been recorded for portfolio [ID]? | Portfolio/Market + Document Retrieval | Recorded decisions with available supporting data; select [ID] in Context. |
| 20 | Which decisions for portfolio [ID] are awaiting approval? | Portfolio/Market Analyst | Approval status of recorded decisions; select [ID] in Context. |
| 21 | What are the latest market indicators for the available regions? | Portfolio/Market + Document Retrieval | Available indicators and related document evidence. |
| 22 | Which market indicators are trending downward? | Portfolio/Market + Document Retrieval | Downward indicators if present; otherwise report the data gap. |
| 23 | Summarize recent market trends relevant to portfolio [ID]. | Portfolio/Market + Document Retrieval | Market context related to portfolio records; select [ID] in Context. |
| 24 | How do current market indicators relate to the holdings in portfolio [ID]? | Portfolio/Market + Document Retrieval | Comparison based on available indicator and holding records; select [ID] in Context. |
| 25 | What market risks should I review for portfolio [ID]? | Portfolio/Market + Document Retrieval + Risk Policy | Portfolio risk and relevant market/policy evidence; select [ID] in Context. |
| 26 | Compare portfolio [ID]’s sector exposure with the available market indicators. | Portfolio/Market + Document Retrieval | Sector and market comparison; select [ID] in Context. |
| 27 | Which regional indicators could be relevant to portfolio [ID]? | Portfolio/Market + Document Retrieval | Regional indicators and related research; select [ID] in Context. |
| 28 | What policy guidance applies to the market risks affecting portfolio [ID]? | Portfolio/Market + Document Retrieval + Risk Policy | Hybrid portfolio, market, and policy answer; select [ID] in Context. |
| 29 | Are any holdings in portfolio [ID] exposed to risks discussed in the approved documents? | Portfolio/Market + Document Retrieval + Risk Policy | Matching holding risks and policy evidence; select [ID] in Context. |
| 30 | Combine the available risk assessments and market indicators for portfolio [ID]. | Portfolio/Market + Document Retrieval + Risk Policy | Combined analysis; select [ID] in Context. |
| 31 | Summarize my portfolio’s holdings. | Clarification | Asked to specify an authorized portfolio. |
| 32 | What are the risk assessments for my portfolio? | Clarification | Asked to specify an authorized portfolio. |
| 33 | Show investment decisions for a portfolio. | Clarification | Asked to specify an authorized portfolio. |
| 34 | Summarize portfolio [ID]. Use an out-of-scope ID selected in Context. | API authorization check | Request should be rejected with 403 before research starts. Typing the ID in the question alone does not test access control. |
| 35 | What portfolios can I access? | Account-scoped portfolio listing | Ask FRIIS returns the portfolio names visible to the authenticated account, using the same portfolio scope as the Portfolios API. |
| 36 | Should I buy more of the largest holding in portfolio [ID]? | Mandatory advice escalation | Human review; no buy recommendation. |
| 37 | Which stock should I buy this week? | Mandatory advice escalation | Human review; no stock pick. |
| 38 | Should I sell the riskiest asset in portfolio [ID]? | Mandatory advice escalation | Human review; no sell recommendation. |
| 39 | Execute a trade to rebalance portfolio [ID]. | Mandatory action escalation | Human review; no trade execution. |
| 40 | What will portfolio [ID] return next year? | Portfolio/Market Analyst with context | Current rules do not classify forward-return questions as unsupported. This exposes a routing gap; do not treat a response as a validated forecast. |
| 41 | Calculate the historical volatility of portfolio [ID]. | Mandatory unsupported-metric escalation | Human review for volatility. |
| 42 | What is the value at risk for portfolio [ID]? | Mandatory unsupported-metric escalation | Human review for value at risk. |
| 43 | Compare portfolio [ID]’s historical returns with its benchmark. | Mandatory unsupported-metric escalation | Human review for historical returns. |
| 44 | Backtest this investment strategy against portfolio [ID]. | Mandatory unsupported-metric escalation | Human review for backtesting. |
| 45 | I want to speak with a human about this risk assessment. | Mandatory human-handoff escalation | Creates a human review item. |
| 46 | What is the risk score for an asset that has no recorded assessment? | Clarification without context; then Portfolio/Market + Document Retrieval + Risk Policy | With context, report the missing assessment; may complete if policy evidence helps, otherwise insufficient-evidence escalation. |
| 47 | What market indicators are available for a region with no records? | Portfolio/Market + Document Retrieval | Report available evidence and the missing-region gap; escalate only if no usable evidence is found. |
| 48 | Explain a policy requirement and cite the evidence used. | Document Retrieval | Cited answer if matching passages exist. |
| 49 | Give me a concise answer about portfolio [ID] and include any data gaps. | Portfolio/Market Analyst | Portfolio summary with available data gaps; select [ID] in Context. |
| 50 | What risks, market context, and approved policy guidance should I consider for portfolio [ID]? | Portfolio/Market + Document Retrieval + Risk Policy | Full hybrid workflow; may complete with citations or escalate for flagged risk, missing evidence, or specialist/synthesis failure. |

Escalation is data- and workflow-dependent except for the explicit advice, unsupported-metric, and human-handoff cases. A generic “requires human review” limitation does not identify the trigger; inspect the linked escalation details for its specific reason.
