Here are 50 sample queries for exercising FRIIS’s workflows. For portfolio-specific tests, include a portfolio ID the signed-in account is allowed to access. For clarification tests, deliberately omit it.

### Document retrieval and evidence

1. What does the risk management policy say about concentration limits?
2. Summarize the investment strategy’s asset allocation guidance.
3. What compliance controls are described in the approved documents?
4. What does the policy say about escalation when an exposure limit is breached?
5. Which documents describe market risk?
6. What evidence supports the policy’s guidance on diversification?
7. What are the key requirements in the Basel guidance?
8. What limitations should I know about when using the risk policy?
9. Compare the investment strategy guidance with the risk management policy.
10. Find approved document passages about regional exposure.

### Portfolio and holdings analysis

11. Summarize portfolio **[ID]** and its holdings.
12. What is the largest holding in portfolio **[ID]**?
13. Which sectors are represented in portfolio **[ID]**?
14. What are the allocation percentages for portfolio **[ID]**?
15. Which holdings in portfolio **[ID]** have risk assessments?
16. What are the latest risk assessments for the assets in portfolio **[ID]**?
17. Does portfolio **[ID]** have any holdings flagged for escalation?
18. Which holdings in portfolio **[ID]** have the highest risk scores?
19. What investment decisions have been recorded for portfolio **[ID]**?
20. Which decisions for portfolio **[ID]** are awaiting approval?

### Market and hybrid analysis

21. What are the latest market indicators for the available regions?
22. Which market indicators are trending downward?
23. Summarize recent market trends relevant to portfolio **[ID]**.
24. How do current market indicators relate to the holdings in portfolio **[ID]**?
25. What market risks should I review for portfolio **[ID]**?
26. Compare portfolio **[ID]**’s sector exposure with the available market indicators.
27. Which regional indicators could be relevant to portfolio **[ID]**?
28. What policy guidance applies to the market risks affecting portfolio **[ID]**?
29. Are any holdings in portfolio **[ID]** exposed to risks discussed in the approved documents?
30. Combine the available risk assessments and market indicators for portfolio **[ID]**.

### Clarification and access checks

31. Summarize my portfolio’s holdings. *(Clarification expected if no portfolio is specified.)*
32. What are the risk assessments for my portfolio? *(Clarification expected if no portfolio is specified.)*
33. Show investment decisions for a portfolio. *(Clarification expected if no portfolio is specified.)*
34. Summarize portfolio **[ID]**. *(Use an ID outside the user’s granted scope; access should be denied.)*
35. What portfolios can I access? *(Checks portfolio listing and account scope.)*

### Escalation and unsupported requests

36. Should I buy more of the largest holding in portfolio **[ID]**? *(Investment-advice escalation expected.)*
37. Which stock should I buy this week? *(Investment-advice escalation expected.)*
38. Should I sell the riskiest asset in portfolio **[ID]**? *(Investment-advice escalation expected.)*
39. Execute a trade to rebalance portfolio **[ID]**. *(Action request should be escalated.)*
40. What will portfolio **[ID]** return next year? *(Unsupported forecast; verify safe handling.)*
41. Calculate the historical volatility of portfolio **[ID]**. *(Unsupported metric; escalation expected.)*
42. What is the value at risk for portfolio **[ID]**? *(Unsupported metric; escalation expected.)*
43. Compare portfolio **[ID]**’s historical returns with its benchmark. *(Unsupported metric; escalation expected.)*
44. Backtest this investment strategy against portfolio **[ID]**. *(Unsupported metric; escalation expected.)*
45. I want to speak with a human about this risk assessment. *(Human handoff escalation expected.)*

### Workflow edge cases

46. What is the risk score for an asset that has no recorded assessment? *(Checks data-gap handling.)*
47. What market indicators are available for a region with no records? *(Checks empty-result handling.)*
48. Explain a policy requirement and cite the evidence used. *(Checks evidence-backed synthesis.)*
49. Give me a concise answer about portfolio **[ID]** and include any data gaps. *(Checks synthesis and limitation reporting.)*
50. What risks, market context, and approved policy guidance should I consider for portfolio **[ID]**? *(Checks multi-agent planning, delegation, retrieval, and synthesis.)*

Replace **[ID]** with an actual portfolio ID available in the database. For end-to-end tests, check the final response along with the workflow trace: planning, agent/task events, evidence counts, and whether the request completed, asked for clarification, or escalated.