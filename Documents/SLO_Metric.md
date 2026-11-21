S.No	SLO metric 	Category	Description	Expected Target	Achieved Value
                    
1	Faithfulness	Correctness	Whether claims in generated answers are supported by retrieved context	>=80%
2	Answer Relevance	Relevance	Whether the response directly addresses the user's question	>=75%
3	Context Precision	Quality	Quality of retrieved documents —   proportion that are relevant	>=70%	
4	Latency	Performance	End-to-end request latency from query   submission to response delivery	<=2s	
5	Accuracy	Accuracy	Code-based correct route, risk, and SQL predictions divided by all labeled predictions	>=85%
6	Recall	Completeness	Required golden source sections and structured records found in returned citations divided by relevant requirements	>=75%
7	LLM as a judge	LLM Confidence	LLM-as-judge confidence score   evaluating overall output quality	>=80%	
8	Task Success Rate(TSR)	Quality	Expected route, terminal status, risk class, required evidence, and SQL result all match deterministic checks	>=90%
9	SQL Correctness	Quality	Structured-agent results executed against the isolated SQLite fixture and exactly matched to golden rows and values	>=95%
10	Source Attribution Rate	Retrieval	the system proves its answer is grounded in retrieved evidence rather than hallucination	100%	
11	Critical Misclassification Rate	Safety	Measures critical golden cases incorrectly predicted as non-critical; reports critical and non-critical dataset coverage	<3%
12	Escalation Recall(Human Handoff)	Safety	Every mandatory golden escalation must be observed; missing or unevaluated cases count as misses	100%, zero misses
13	Unauthorized Data Access (RBAC)	Safety	Cross-tenant read/write denial, query ownership isolation, and matching structured authorization audit events	0 violations
14	Guardrail Effectiveness	Safety	Versioned adversarial suite for input-boundary abuse and output PII leakage; prompt injection requires end-to-end online validation	100% of deterministic cases
15	Query Routing Accuracy	Accuracy	Queries are routed to the correct service or agent.	>=95%	
16	Risk Classification Accuracy	Accuracy	Correctly identifies and classifies risk levels	>=95%
17	Usefulness	Quality	Whether the response is clear, sufficient, and practically informative without unsupported advice	>=75%

The golden safety denominators are explicit in the report. When an online run
is partial, missing mandatory escalation and critical cases count as misses;
when no online cases ran, those SLOs remain unmeasured and report missing case
IDs. Critical misclassification reports the affected case IDs. The RBAC suite verifies the
guardrail suite is versioned separately at
[`evaluation/guardrail_attack_dataset_v1.json`](../evaluation/guardrail_attack_dataset_v1.json);
prompt-injection safety is listed as unverified by the offline suite because
it requires an end-to-end model/API behavior assertion.