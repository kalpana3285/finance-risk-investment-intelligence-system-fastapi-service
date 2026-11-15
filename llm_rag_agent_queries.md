# Queries for LLM, agent, and RAG responses

Use these examples to exercise document retrieval, specialist agents, and
evidence-based LLM synthesis without intentionally requesting a human handoff.
They are prompts to try, not guarantees: a completed response depends on the
relevant approved documents being ingested, required portfolio or market data
being present, and the configured Azure OpenAI services being available.

For **document-only** questions, leave Portfolio set to **No specific
portfolio**. For **hybrid portfolio** questions, select an authorized portfolio
in the dropdown and replace `[ID]` with that portfolio's ID. These hybrid
questions avoid structured risk-review triggers; they request holdings or
market context together with approved investment or market research.

## Document retrieval and synthesis

1. What concentration caps are stated in the approved investment documents?
2. Summarize the approved strategy recommendations for diversification and major asset classes.
3. What compliance controls are described in the approved documents?
4. What does the Basel III guidance say about governance and monitoring?
5. What reporting cadence do the approved investment documents recommend?
6. What guidance do approved documents give about currencies and hedging?
7. How do investment strategy documents recommend spreading investments across asset classes, sectors, and issuers?
8. What guidance is available for liquidity and periodic rebalancing?
9. Which approved documents discuss regional market conditions, and what do they say?
10. Summarize the investment categories and benchmarks listed in the approved monitoring guide.

## Market analysis with retrieved research

11. What are the latest available market indicators by region, and what context does the approved market research provide?
12. Compare the recorded inflation and interest-rate indicators across regions and summarize relevant approved research.
13. Which regions have market indicator records, and what regional context is available in the approved documents?
14. Summarize the available market indicators alongside the approved guidance for interpreting market conditions.

## Portfolio analysis with RAG context

For these questions, select the portfolio in the dropdown. The selected ID is
also added to the submitted query.

15. Summarize portfolio [ID]'s holdings and relate them to the approved investment strategy guidance.
16. Compare portfolio [ID]'s sector composition with the available regional market indicators and approved market research.
17. Summarize the asset types in portfolio [ID] and compare them with the approved asset-allocation guidance.
18. Describe portfolio [ID]'s reported benchmark and summarize the relevant discussion in the approved investment guide.
19. Compare portfolio [ID]'s holdings with the available market indicators, citing relevant approved market research.
20. Summarize the reported holdings and allocation mix for portfolio [ID], and identify which details the approved strategy documents help contextualize.

## To get a grounded response

- Ensure approved documents have been ingested into `document_chunks` and are
  enabled for retrieval. Uploaded files should appear in the approved-source
  list as well as have searchable chunks.
- For portfolio questions, select an accessible portfolio. For market questions,
  the response can only use regions and indicators present in the database.
- A prompt may still be escalated if retrieval finds no usable passages, the
  supplied portfolio data contains a record explicitly flagged for review, or
  a required service or validation step fails. The response now shows the
  escalation reason and data gaps when that happens.
