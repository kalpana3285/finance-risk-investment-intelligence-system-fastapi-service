from math import ceil
from types import SimpleNamespace

from evaluation.dataset_evaluation import (
    add_items,
    ensure_dataset,
    get_dataset_name,
    load_golden_dataset,
    upload_dataset,
)


class FakeLangfuse:
    def __init__(self) -> None:
        self.dataset_names: set[str] = set()
        self.dataset_creations: list[dict] = []
        self.items_by_id: dict[str, dict] = {}
        self.api = SimpleNamespace(
            datasets=SimpleNamespace(list=self.list_datasets)
        )

    def list_datasets(self, *, page: int, limit: int):
        names = sorted(self.dataset_names)
        start = (page - 1) * limit
        data = [SimpleNamespace(name=name) for name in names[start : start + limit]]
        total_pages = max(1, ceil(len(names) / limit))
        return SimpleNamespace(
            data=data,
            meta=SimpleNamespace(total_pages=total_pages),
        )

    def create_dataset(self, **kwargs) -> None:
        self.dataset_creations.append(kwargs)
        self.dataset_names.add(kwargs["name"])

    def create_dataset_item(self, **kwargs) -> None:
        self.items_by_id[kwargs["id"]] = kwargs


def test_load_golden_dataset_reads_all_50_cases_and_category_counts():
    dataset = load_golden_dataset()

    assert len(dataset["cases"]) == 50
    assert dataset["category_counts"] == {
        "policy_rag": 15,
        "portfolio_sql": 10,
        "hybrid_risk": 10,
        "high_risk_decision": 10,
        "escalation": 5,
    }


def test_upload_maps_golden_cases_and_is_safe_to_rerun():
    dataset = load_golden_dataset()
    langfuse = FakeLangfuse()
    dataset_name = get_dataset_name(dataset)

    assert dataset_name == "friis-golden-evaluation-v1.0.0"
    assert upload_dataset(langfuse, dataset) == 50
    assert upload_dataset(langfuse, dataset) == 50

    assert len(langfuse.dataset_creations) == 1
    assert len(langfuse.items_by_id) == 50

    sql_case = next(
        item
        for item in langfuse.items_by_id.values()
        if item["metadata"]["case_id"] == "SQL-010"
    )
    assert sql_case["input"] == {
        "question": "Retrieve portfolio 999 from the fixture.",
        "portfolio_id": 999,
    }
    assert sql_case["expected_output"]["expected_result"] is None
    assert sql_case["expected_output"]["expected_route"] == "structured_data"
    assert sql_case["expected_output"]["expected_risk_class"] == "not_applicable"
    assert sql_case["expected_output"]["expected_escalation"] is False
    expected_sql_case = next(
        case for case in dataset["cases"] if case["id"] == "SQL-010"
    )
    assert (
        sql_case["expected_output"]["answer_rubric"]
        == expected_sql_case["answer_rubric"]
    )
    assert (
        sql_case["expected_output"]["required_evidence"]
        == expected_sql_case["required_evidence"]
    )
    assert sql_case["metadata"] == {
        "case_id": "SQL-010",
        "category": "portfolio_sql",
        "dataset_version": dataset["version"],
        "review_status": "draft_requires_domain_review",
    }

    no_portfolio_case = next(
        item
        for item in langfuse.items_by_id.values()
        if item["metadata"]["case_id"] == "SQL-008"
    )
    assert no_portfolio_case["input"]["portfolio_id"] is None


def test_ensure_dataset_does_not_create_an_existing_version():
    dataset = load_golden_dataset()
    langfuse = FakeLangfuse()
    dataset_name = get_dataset_name(dataset)
    langfuse.dataset_names.add(dataset_name)

    assert ensure_dataset(langfuse, dataset) == dataset_name
    assert langfuse.dataset_creations == []


def test_add_items_upserts_stable_ids():
    dataset = load_golden_dataset()
    langfuse = FakeLangfuse()
    dataset_name = get_dataset_name(dataset)

    assert add_items(langfuse, dataset_name, dataset) == 50
    first_ids = set(langfuse.items_by_id)
    assert add_items(langfuse, dataset_name, dataset) == 50

    assert set(langfuse.items_by_id) == first_ids
    assert len(first_ids) == 50
