# FRIIS Multi-Agent Workflow

The diagram shows the implemented LangGraph query workflow. The planner is deterministic; the supervisor delegates only the specialists needed for a query. The optional tool-enabled Finance agent is a separate endpoint and is not part of this graph.

```mermaid
flowchart TD
    U[Analyst] --> API[API authentication and authorization]
    API --> P[Deterministic query planner]

    P -->|Clarification needed| C[Ask for clarification]
    P -->|Mandatory escalation| H[Create human handoff]
    P -->|Select up to 3 specialists| S[LangGraph Supervisor]

    S --> D[Document Retrieval]
    S --> M[Portfolio / Market Analyst]
    D --> J[Join specialist results]
    M --> J

    J -->|Risk specialist planned| R[Risk & Policy Analyst]
    J -->|No risk specialist planned| V[Check results and evidence]
    R --> V

    V -->|Correctable failure| F[Bounded reflection and retry]
    F --> V
    V --> E[Assemble and validate evidence]

    E -->|Insufficient, conflicting, or review required| H
    E -->|Sufficient evidence| Y[Azure OpenAI synthesis]
    Y -->|Valid citations| A[Attributed answer]
    Y -->|Synthesis or citation failure| H
    H --> HR[Human reviewer]
```
