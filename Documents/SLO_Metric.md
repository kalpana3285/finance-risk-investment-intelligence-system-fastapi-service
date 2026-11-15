S.No	SLO metric 	Category	Description	Expected Target	Achieved Value
                    
1	Faithfulness	Correctness	Correctness of generated answers	>=80%	
2	Answer Relevance	Usefullness	Usefulness of the retrieved chunks and   generated output to the query	>=75%	
3	Context Precision	Quality	Quality of retrieved documents —   proportion that are relevant	>=70%	
4	Latency	Performance	End-to-end request latency from query   submission to response delivery	<=2s	
5	Accuracy	Accuracy	Overall correctness of the system’s   answers against ground truth	>=85%	
6	Recall	Completeness	Completeness — proportion of relevant   documents successfully retrieved	>=75%	
7	LLM as a judge	LLM Confidence	LLM-as-judge confidence score   evaluating overall output quality	>=80%	
8	Task Succes Rate(TSR)	Quality	Measures whether the system produced a correct outcome	>=90%	
9	SQL Correctness	Quality	Measures whether parameterized query results match ground truth on the golden set	>=95%	
10	Source Attribution Rate	Retrieval	the system proves its answer is grounded in retrieved evidence rather than hallucination	100%	
11	Critical Misclassification Rate	Safety	Measures how often a Critical ticket is not classified as Critical (false negative	<3%	
12	Escalation Recall(Human Handoff)	Safety	100% recall is the only acceptable target — missing a single mandatory escalation is a system failure, not a statistical outlier.	100%	
13	Unautorized Data Access(RBAC)	Safety	Any cross-customer data access is a data breach with regulatory and legal consequences	0 violations	
14	Guardrail effectivness	Safety	Measured against defined attack types	100%	
15	Query Routing Accuracy	Accuracy	Queries are routed to the correct service or agent.	>=95%	
16	Risk Classification Accuracy	Accuracy	Correctly identifies and classifies risk levels	>=95%	