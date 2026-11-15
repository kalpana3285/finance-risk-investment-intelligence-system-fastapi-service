"""LangGraph orchestration for FRIIS's bounded research workflow."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Send

from schemas import QueryStatus
from agents.control_plane import (
    MAX_SPECIALIST_ATTEMPTS,
    MAX_WORKFLOW_CORRECTIONS,
    MAX_EVIDENCE_ITEMS,
    AgentEvidence,
    ControlPlaneError,
    CorrectionMode,
    DocumentRetrievalAgent,
    OrchestrationResult,
    PortfolioMarketAnalystAgent,
    QueryContext,
    QueryPlan,
    RiskPolicyAnalystAgent,
    SpecialistResult,
    SupervisorAgent,
    WorkflowPhase,
    SynthesisCorrectionState,
    WorkflowTask,
)


def _merge_maps(left: dict, right: dict) -> dict:
    """Merge concurrent specialist updates by agent name."""
    return left | right


class WorkflowGraphState(TypedDict, total=False):
    """Typed, request-scoped data shared across orchestration nodes."""

    phase: WorkflowPhase | None
    plan: QueryPlan
    tasks: tuple[WorkflowTask, ...]
    active_task: WorkflowTask
    specialist_results: Annotated[
        dict[str, SpecialistResult], _merge_maps
    ]
    specialist_errors: Annotated[
        dict[str, str | None], _merge_maps
    ]
    attempt_number: int
    correction_used: bool
    correction_target: str | None
    correction_mode: CorrectionMode | None
    correction_reason: str | None
    task_attempts: dict[str, int]
    next_action: str
    terminal_reason: str
    evidence: tuple[AgentEvidence, ...]
    data_gaps: list[str]
    attempted_steps: list[str]
    synthesis: object
    synthesis_error: str | None
    result: OrchestrationResult


def compile_workflow(supervisor: SupervisorAgent):
    """Build the supervisor graph while reusing FRIIS's existing agents/contracts."""

    async def transition(
        state: WorkflowGraphState,
        phase: WorkflowPhase,
        query_id: str,
    ) -> WorkflowPhase:
        previous = state.get("phase")
        await supervisor._emit(
            "workflow_phase",
            supervisor.name,
            {
                "query_id": query_id,
                "from": previous.value if previous is not None else "created",
                "to": phase.value,
            },
        )
        return phase

    async def plan_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        context = runtime.context
        phase = await transition(state, WorkflowPhase.PLANNING, context.query_id)
        plan = supervisor.planner.create_plan(context)
        manager_names = {RiskPolicyAnalystAgent.name}
        child_names = tuple(
            name for name in plan.specialists if name not in manager_names
        )
        tasks = tuple(
            supervisor._workflow_task(
                index,
                name,
                context,
                child_agent_names=child_names,
            )
            for index, name in enumerate(plan.specialists, start=1)
        )
        await supervisor._emit(
            "plan_created",
            supervisor.name,
            {
                "intent": plan.intent,
                "specialists": list(plan.specialists),
                "tasks": [task.model_dump(mode="json") for task in tasks],
                "correction_budget": MAX_WORKFLOW_CORRECTIONS,
            },
        )
        missing_agents = set(plan.specialists) - set(supervisor.agents)
        if not plan.clarification_question and not plan.mandatory_escalation_reason and missing_agents:
            raise ControlPlaneError(
                "Required specialist is not configured: "
                + ", ".join(sorted(missing_agents))
            )
        return {
            "phase": phase,
            "plan": plan,
            "tasks": tasks,
            "specialist_results": {},
            "specialist_errors": {},
            "attempt_number": 1,
            "correction_used": False,
            "correction_target": None,
            "correction_mode": None,
            "correction_reason": None,
            "task_attempts": {},
        }

    def route_plan(state: WorkflowGraphState) -> str:
        plan = state["plan"]
        if plan.clarification_question:
            return "clarify"
        if plan.mandatory_escalation_reason:
            return "escalate_plan"
        return "start_delegation"

    async def clarify_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        phase = await transition(
            state, WorkflowPhase.NEEDS_CLARIFICATION, runtime.context.query_id
        )
        return {
            "phase": phase,
            "result": OrchestrationResult(
                status=QueryStatus.NEEDS_CLARIFICATION,
                clarification_question=state["plan"].clarification_question,
            ),
        }

    async def escalate_plan_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        phase = await transition(
            state, WorkflowPhase.ESCALATED, runtime.context.query_id
        )
        plan = state["plan"]
        return {
            "phase": phase,
            "result": supervisor._escalate(
                plan.mandatory_escalation_reason or "The request requires review.",
                data_gaps=plan.data_gaps,
                attempted=("Classify the request against system boundaries.",),
            ),
        }

    async def start_delegation_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        phase = await transition(
            state, WorkflowPhase.ACTING, runtime.context.query_id
        )
        attempts = dict(state.get("task_attempts", {}))
        for task in state["tasks"]:
            attempts[task.task_id] = 1
            await supervisor._emit(
                "task_delegated",
                task.manager_agent,
                task.model_dump(mode="json") | {"attempt": 1},
            )
        return {"phase": phase, "task_attempts": attempts}

    def dispatch_leaf_specialists(state: WorkflowGraphState):
        manager_names = {RiskPolicyAnalystAgent.name}
        leaf_tasks = [
            task for task in state["tasks"] if task.agent_name not in manager_names
        ]
        if leaf_tasks:
            return [
                Send("run_leaf_specialist", {"active_task": task})
                for task in leaf_tasks
            ]
        if any(task.agent_name in manager_names for task in state["tasks"]):
            return "run_manager_specialist"
        return "check_attempt"

    async def run_leaf_specialist_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        task = state["active_task"]
        agent = supervisor.agents[task.agent_name]
        context = runtime.context
        specialist_context = QueryContext(
            query_id=context.query_id,
            question=context.question,
            portfolio_id=context.portfolio_id,
            conversation_context=context.conversation_context,
            authorized_portfolio_ids=context.authorized_portfolio_ids,
            all_portfolios_access=context.all_portfolios_access,
            principal_roles=context.principal_roles,
            task_objective=task.objective,
        )
        try:
            result = await supervisor._run_specialist(agent, specialist_context)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return {"specialist_errors": {task.agent_name: type(exc).__name__}}
        return {"specialist_results": {task.agent_name: result}}

    def route_after_leaves(state: WorkflowGraphState) -> str:
        if any(
            task.agent_name == RiskPolicyAnalystAgent.name
            for task in state["tasks"]
        ):
            return "run_manager_specialist"
        return "check_attempt"

    async def run_manager_specialist_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        task = next(
            task
            for task in state["tasks"]
            if task.agent_name == RiskPolicyAnalystAgent.name
        )
        context = runtime.context
        child_results = tuple(
            state["specialist_results"][name]
            for name in state["plan"].specialists
            if name != RiskPolicyAnalystAgent.name
            and name in state["specialist_results"]
        )
        manager_context = QueryContext(
            query_id=context.query_id,
            question=context.question,
            portfolio_id=context.portfolio_id,
            conversation_context=context.conversation_context,
            authorized_portfolio_ids=context.authorized_portfolio_ids,
            all_portfolios_access=context.all_portfolios_access,
            principal_roles=context.principal_roles,
            child_results=child_results,
            task_objective=task.objective,
        )
        try:
            result = await supervisor._run_specialist(
                supervisor.agents[task.agent_name], manager_context
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return {"specialist_errors": {task.agent_name: type(exc).__name__}}
        return {"specialist_results": {task.agent_name: result}}

    async def check_attempt_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        context = runtime.context
        phase = await transition(state, WorkflowPhase.CHECKING, context.query_id)
        plan_names = state["plan"].specialists
        results = state.get("specialist_results", {})
        errors = {
            name: error
            for name, error in state.get("specialist_errors", {}).items()
            if error is not None
        }
        attempt = state["attempt_number"]
        if attempt == 1:
            for name in plan_names:
                result = results.get(name)
                error = errors.get(name)
                await supervisor._emit(
                    "task_checked",
                    name,
                    {
                        "accepted": result is not None and error is None,
                        "attempt": 1,
                        **(
                            {
                                "reason": "specialist execution or validation failed"
                            }
                            if error is not None
                            else {
                                "evidence_count": len(result.evidence),
                                "data_gap_count": len(result.data_gaps),
                                "delegated_agents": list(result.delegated_agents),
                            }
                            if result is not None
                            else {"reason": "specialist returned no result"}
                        ),
                    },
                )
            candidate = next((name for name in plan_names if name in errors), None)
            mode = CorrectionMode.RETRY_READ_ONLY
            reason = "The first attempt failed validation or execution."
            if candidate is None:
                candidate = next(
                    (
                        name
                        for name in plan_names
                        if name == DocumentRetrievalAgent.name
                        and name in results
                        and not results[name].evidence
                    ),
                    None,
                )
                mode = CorrectionMode.FOCUS_RETRIEVAL
                reason = "No approved document passages matched the initial retrieval."
            if candidate is not None:
                return {
                    "phase": phase,
                    "correction_target": candidate,
                    "correction_mode": mode,
                    "correction_reason": reason,
                    "next_action": "retry",
                }
            return {"phase": phase, "next_action": "finalize"}

        target = state["correction_target"]
        if target is None:
            return {"phase": phase, "next_action": "finalize"}
        result = results.get(target)
        error = errors.get(target)
        await supervisor._emit(
            "task_checked",
            target,
            {
                "accepted": result is not None and error is None,
                "attempt": attempt,
                **(
                    {"reason": "specialist retry failed"}
                    if error is not None
                    else {
                        "evidence_count": len(result.evidence),
                        "data_gap_count": len(result.data_gaps),
                        "delegated_agents": list(result.delegated_agents),
                    }
                    if result is not None
                    else {"reason": "specialist retry returned no result"}
                ),
            },
        )
        should_retry = error is not None or (
            state.get("correction_mode") == CorrectionMode.FOCUS_RETRIEVAL
            and result is not None
            and not result.evidence
        )
        retry_reason = state.get("correction_reason")
        if (
            state.get("correction_mode") == CorrectionMode.FOCUS_RETRIEVAL
            and result is not None
            and not result.evidence
        ):
            retry_reason = "The retry returned no approved document passages."
        return {
            "phase": phase,
            "correction_reason": retry_reason,
            "next_action": (
                "retry"
                if should_retry and attempt < MAX_SPECIALIST_ATTEMPTS
                else "finalize"
            ),
        }

    async def reflection_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        next_attempt = state["attempt_number"] + 1
        task = next(
            task
            for task in state["tasks"]
            if task.agent_name == state["correction_target"]
        )
        phase = await transition(
            state, WorkflowPhase.REFLECTING, runtime.context.query_id
        )
        await supervisor._emit(
            "bounded_reflection",
            task.agent_name,
            {
                "task_id": task.task_id,
                "attempt": next_attempt,
                "correction_mode": state["correction_mode"].value,
                "reason": state.get("correction_reason"),
                "scope_unchanged": True,
            },
        )
        attempts = dict(state.get("task_attempts", {}))
        attempts[task.task_id] = next_attempt
        return {
            "phase": phase,
            "attempt_number": next_attempt,
            "correction_used": True,
            "task_attempts": attempts,
        }

    async def retry_specialist_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        target = state["correction_target"]
        task = next(task for task in state["tasks"] if task.agent_name == target)
        phase = await transition(state, WorkflowPhase.ACTING, runtime.context.query_id)
        context = runtime.context
        child_results = (
            tuple(
                state["specialist_results"][name]
                for name in state["plan"].specialists
                if name != RiskPolicyAnalystAgent.name
                and name in state["specialist_results"]
            )
            if target == RiskPolicyAnalystAgent.name
            else ()
        )
        retry_context = QueryContext(
            query_id=context.query_id,
            question=context.question,
            portfolio_id=context.portfolio_id,
            conversation_context=context.conversation_context,
            authorized_portfolio_ids=context.authorized_portfolio_ids,
            all_portfolios_access=context.all_portfolios_access,
            principal_roles=context.principal_roles,
            task_objective=task.objective,
            correction_mode=state.get("correction_mode"),
            child_results=child_results,
        )
        try:
            result = await supervisor._run_specialist(
                supervisor.agents[target], retry_context
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return {
                "phase": phase,
                "specialist_errors": {target: type(exc).__name__},
            }
        return {
            "phase": phase,
            "specialist_results": {target: result},
            "specialist_errors": {target: None},
        }

    async def assemble_evidence_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        plan = state["plan"]
        result_map = state.get("specialist_results", {})
        error_map = {
            name: value
            for name, value in state.get("specialist_errors", {}).items()
            if value is not None
        }
        results = [result_map[name] for name in plan.specialists if name in result_map]
        errors = [
            f"{name} did not return valid evidence after "
            f"{MAX_SPECIALIST_ATTEMPTS} attempts."
            for name in plan.specialists
            if name in error_map
        ]
        evidence_by_id: dict[str, AgentEvidence] = {}
        conflicts: list[str] = []
        for result in results:
            for item in result.evidence:
                existing = evidence_by_id.get(item.evidence_id)
                if existing is not None and existing != item:
                    conflicts.append(item.evidence_id)
                else:
                    evidence_by_id.setdefault(item.evidence_id, item)
        evidence = tuple(evidence_by_id.values())[:MAX_EVIDENCE_ITEMS]
        gaps = [
            gap for result in results for gap in (*result.data_gaps, *result.warnings)
        ] + errors
        if conflicts:
            gaps.append("Conflicting specialist results shared an evidence identifier.")
        attempted = [f"Run {name}." for name in plan.specialists]
        target = state.get("correction_target")
        if target:
            attempted.append(
                f"Apply up to {MAX_WORKFLOW_CORRECTIONS} bounded retries to {target}."
            )
        reason = ""
        if errors:
            reason = "A required specialist did not complete successfully."
        elif conflicts:
            reason = "Specialists returned conflicting results for the same evidence identifier."
        elif any(result.requires_human_review for result in results):
            reason = "A specialist identified a record requiring human review."
        elif not evidence:
            reason = "The system could not find sufficient evidence to answer safely."
            if not gaps:
                gaps.append("No verifiable evidence was returned.")
        route = "escalate" if reason else (
            "portfolio_access"
            if plan.intent == "portfolio_access_listing"
            else "synthesize"
        )
        await supervisor._emit(
            "evidence_route_selected",
            supervisor.name,
            {
                "query_id": runtime.context.query_id,
                "route": route,
                "specialist_count": len(results),
                "evidence_count": len(evidence),
                "data_gap_count": len(gaps),
            },
        )
        return {
            "evidence": evidence,
            "data_gaps": gaps,
            "attempted_steps": attempted,
            "terminal_reason": reason,
            "next_action": route,
        }

    async def escalate_evidence_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        phase = await transition(
            state, WorkflowPhase.ESCALATED, runtime.context.query_id
        )
        return {
            "phase": phase,
            "result": supervisor._escalate(
                state["terminal_reason"],
                evidence=state.get("evidence", ()),
                attempted=state.get("attempted_steps", []),
                data_gaps=state.get("data_gaps", []),
            ),
        }

    async def portfolio_access_answer_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        evidence = state["evidence"]
        scope_evidence = evidence[0]
        try:
            scope_data = json.loads(scope_evidence.content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ControlPlaneError(
                "Authenticated portfolio scope evidence was malformed."
            ) from exc
        role_names = [
            role.replace("_", " ").title() for role in runtime.context.principal_roles
        ] or ["No role claim recorded"]
        accessible_names = [
            item["portfolio_name"]
            for item in scope_data.get("accessible_portfolios", [])
            if isinstance(item, dict) and item.get("portfolio_name")
        ]
        if accessible_names:
            portfolio_text = "\n".join(f"- {name}" for name in accessible_names)
            answer = (
                f"Principal role(s): {', '.join(role_names)}.\n\n"
                f"Accessible portfolios ({len(accessible_names)}):\n{portfolio_text}"
            )
        else:
            answer = (
                f"Principal role(s): {', '.join(role_names)}.\n\n"
                "No portfolios are currently accessible to this account."
            )
        phase = await transition(
            state, WorkflowPhase.COMPLETED, runtime.context.query_id
        )
        return {
            "phase": phase,
            "result": OrchestrationResult(
                status=QueryStatus.COMPLETED,
                answer=answer,
                citations=(scope_evidence.citation,),
                limitations=tuple(state.get("data_gaps", [])),
            ),
        }

    async def synthesis_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        phase = await transition(
            state, WorkflowPhase.SYNTHESIZING, runtime.context.query_id
        )
        correction_state = SynthesisCorrectionState(
            phase=phase,
            correction_used=state.get("correction_used", False),
            correction_target=state.get("correction_target"),
            task_attempts=dict(state.get("task_attempts", {})),
        )
        try:
            synthesis = await supervisor._synthesize(
                runtime.context,
                state["evidence"],
                allow_correction=not correction_state.correction_used,
                workflow_state=correction_state,
            )
        except ControlPlaneError as exc:
            return {
                "phase": phase,
                "synthesis_error": str(exc),
                "correction_used": correction_state.correction_used,
                "correction_target": correction_state.correction_target,
            }
        await supervisor._emit(
            "synthesis_completed",
            "Response synthesis",
            {
                "query_id": runtime.context.query_id,
                "status": "completed",
                "citation_count": len(synthesis.citation_ids),
            },
        )
        return {
            "phase": phase,
            "synthesis": synthesis,
            "synthesis_error": None,
            "correction_used": correction_state.correction_used,
            "correction_target": correction_state.correction_target,
        }

    def route_synthesis(state: WorkflowGraphState) -> str:
        return "escalate_synthesis" if state.get("synthesis_error") else "finalize"

    async def escalate_synthesis_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        phase = await transition(
            state, WorkflowPhase.ESCALATED, runtime.context.query_id
        )
        attempted = list(state.get("attempted_steps", []))
        attempted.append("Synthesize and validate evidence.")
        if state.get("correction_target") == "response synthesis":
            attempted.append("Apply one bounded correction attempt to response synthesis.")
        return {
            "phase": phase,
            "result": supervisor._escalate(
                "Evidence synthesis or citation validation failed.",
                evidence=state.get("evidence", ()),
                attempted=attempted,
                data_gaps=state.get("data_gaps", [])
                + [state.get("synthesis_error", "Synthesis failed.")],
            ),
        }

    async def finalize_node(
        state: WorkflowGraphState,
        runtime: Runtime[QueryContext],
    ) -> dict:
        synthesis = state["synthesis"]
        if not synthesis.citation_ids:
            phase = await transition(
                state, WorkflowPhase.ESCALATED, runtime.context.query_id
            )
            result = supervisor._escalate(
                "No valid supporting citations were produced.",
                evidence=state.get("evidence", ()),
                attempted=state.get("attempted_steps", [])
                + ["Validate synthesis citations."],
                data_gaps=state.get("data_gaps", [])
                + ["A completed answer must cite retrieved evidence."],
            )
            return {"phase": phase, "result": result}

        evidence_by_id = {
            item.evidence_id: item for item in state.get("evidence", ())
        }
        citations = tuple(
            evidence_by_id[citation_id].citation
            for citation_id in synthesis.citation_ids
        )
        limitations = list(synthesis.limitations)
        for gap in state.get("data_gaps", []):
            if gap not in limitations:
                limitations.append(gap)
        if not any("educational" in item.lower() for item in limitations):
            limitations.append(
                "FRIIS uses synthetic educational data and is not investment advice."
            )
        answer = synthesis.answer
        for number, citation_id in enumerate(synthesis.citation_ids, start=1):
            answer = answer.replace(citation_id, str(number))
        answer = re.sub(
            r"([^\n])\s+(?=\([a-z]\)\s)",
            r"\1\n\n",
            answer,
            flags=re.IGNORECASE,
        )
        phase = await transition(
            state, WorkflowPhase.COMPLETED, runtime.context.query_id
        )
        return {
            "phase": phase,
            "result": OrchestrationResult(
                status=QueryStatus.COMPLETED,
                answer=answer,
                citations=citations,
                limitations=tuple(limitations),
            ),
        }

    builder = StateGraph(WorkflowGraphState, context_schema=QueryContext)
    builder.add_node("plan", plan_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("escalate_plan", escalate_plan_node)
    builder.add_node("start_delegation", start_delegation_node)
    builder.add_node("run_leaf_specialist", run_leaf_specialist_node)
    builder.add_node("after_leaf_specialists", lambda _state: {})
    builder.add_node("run_manager_specialist", run_manager_specialist_node)
    builder.add_node("check_attempt", check_attempt_node)
    builder.add_node("reflect", reflection_node)
    builder.add_node("retry_specialist", retry_specialist_node)
    builder.add_node("assemble_evidence", assemble_evidence_node)
    builder.add_node("escalate_evidence", escalate_evidence_node)
    builder.add_node("portfolio_access_answer", portfolio_access_answer_node)
    builder.add_node("synthesize", synthesis_node)
    builder.add_node("escalate_synthesis", escalate_synthesis_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "plan")
    builder.add_conditional_edges(
        "plan",
        route_plan,
        {
            "clarify": "clarify",
            "escalate_plan": "escalate_plan",
            "start_delegation": "start_delegation",
        },
    )
    builder.add_edge("clarify", END)
    builder.add_edge("escalate_plan", END)
    builder.add_conditional_edges("start_delegation", dispatch_leaf_specialists)
    builder.add_edge("run_leaf_specialist", "after_leaf_specialists")
    builder.add_conditional_edges(
        "after_leaf_specialists",
        route_after_leaves,
        {
            "run_manager_specialist": "run_manager_specialist",
            "check_attempt": "check_attempt",
        },
    )
    builder.add_edge("run_manager_specialist", "check_attempt")
    builder.add_conditional_edges(
        "check_attempt",
        lambda state: state["next_action"],
        {"retry": "reflect", "finalize": "assemble_evidence"},
    )
    builder.add_edge("reflect", "retry_specialist")
    builder.add_edge("retry_specialist", "check_attempt")
    builder.add_conditional_edges(
        "assemble_evidence",
        lambda state: state["next_action"],
        {
            "escalate": "escalate_evidence",
            "portfolio_access": "portfolio_access_answer",
            "synthesize": "synthesize",
        },
    )
    builder.add_edge("escalate_evidence", END)
    builder.add_edge("portfolio_access_answer", END)
    builder.add_conditional_edges(
        "synthesize",
        route_synthesis,
        {"escalate_synthesis": "escalate_synthesis", "finalize": "finalize"},
    )
    builder.add_edge("escalate_synthesis", END)
    builder.add_edge("finalize", END)
    return builder.compile()


async def run_workflow(
    supervisor: SupervisorAgent,
    context: QueryContext,
) -> OrchestrationResult:
    """Run one query through the compiled, bounded LangGraph workflow."""
    try:
        state = await asyncio.wait_for(
            supervisor._graph.ainvoke(
                {
                    "phase": None,
                    "specialist_results": {},
                    "specialist_errors": {},
                    "attempt_number": 1,
                    "correction_used": False,
                    "correction_target": None,
                    "correction_mode": None,
                    "correction_reason": None,
                    "task_attempts": {},
                },
                context=context,
            ),
            timeout=supervisor.workflow_timeout_seconds,
        )
    except TimeoutError:
        await supervisor._emit("workflow_timeout", supervisor.name, {})
        return supervisor._escalate(
            "The bounded analysis workflow exceeded its time limit.",
            data_gaps=("Workflow deadline exceeded.",),
            attempted=("Create a bounded evidence plan.",),
        )
    result = state.get("result")
    if not isinstance(result, OrchestrationResult):
        raise ControlPlaneError("The LangGraph workflow completed without a result.")
    return result
