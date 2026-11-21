import importlib
import os


os.environ["LANGFUSE_ENABLED"] = "false"
langfuse_tracing = importlib.import_module("services.langfuse_tracing")


class _TestManagedPrompt:
    def __init__(
        self,
        *,
        name: str,
        prompt_type: str,
        label: str | None,
    ) -> None:
        self.name = name
        self.version = {
            "friis-finance-synthesis": 1,
            "friis-finance-tool-agent": 1,
            "friis-pdf-visual-caption": 1,
            "friis-query-result-evaluator": 2,
            "friis-finance-rag-evaluator": 2,
        }[name]
        self.labels = [label] if label is not None else []
        self.variables = {
            "friis-finance-synthesis": ["request_payload"],
            "friis-finance-tool-agent": [],
            "friis-pdf-visual-caption": ["page_image"],
            "friis-query-result-evaluator": ["evaluation_payload"],
            "friis-finance-rag-evaluator": ["evaluation_payload"],
        }[name]
        self.is_chat = prompt_type == "chat" or name in {
            "friis-finance-synthesis",
            "friis-query-result-evaluator",
            "friis-finance-rag-evaluator",
        }

    def get_langchain_prompt(self):
        if self.is_chat:
            variable = self.variables[0]
            return [
                (
                    "system",
                    "Test-managed instructions for untrusted data, faithfulness, "
                    "correctness, answer_relevance, usefulness, context_precision, "
                    "and risk classification accuracy.",
                ),
                ("human", "{" + variable + "}"),
            ]
        variable = self.variables[0] if self.variables else ""
        return "Test-managed prompt instructions" + (
            " {" + variable + "}" if variable else ""
        )


def _fetch_test_managed_prompt(
    *,
    name: str,
    prompt_type: str,
    label: str | None,
) -> _TestManagedPrompt:
    return _TestManagedPrompt(
        name=name,
        prompt_type=prompt_type,
        label=label,
    )


_original_fetch_prompt = langfuse_tracing.fetch_prompt
langfuse_tracing.fetch_prompt = _fetch_test_managed_prompt
try:
    for module_name in (
        "agents.control_plane",
        "agents.tool_enabled_agent",
        "evaluation.slo_evaluation",
        "services.multimodal_processing",
    ):
        importlib.import_module(module_name)
finally:
    langfuse_tracing.fetch_prompt = _original_fetch_prompt
