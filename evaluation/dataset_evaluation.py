"""Upload the versioned FRIIS golden evaluation dataset to Langfuse."""

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

GOLDEN_DATASET_PATH = Path(__file__).with_name("golden_dataset_v1.json")
DATASET_PAGE_SIZE = 100


def get_langfuse_client() -> Langfuse:
    """Initialize the Langfuse client from environment variables."""
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not secret_key or not public_key:
        raise RuntimeError(
            "LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY must be set in environment."
        )

    return Langfuse(secret_key=secret_key, public_key=public_key, host=host)


def load_golden_dataset(
    path: Path = GOLDEN_DATASET_PATH,
) -> dict[str, Any]:
    """Load and validate the golden dataset manifest and all of its cases."""
    with path.open(encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)

    if not isinstance(dataset, dict):
        raise ValueError("The golden dataset must be a JSON object.")

    cases = dataset.get("cases")
    if not isinstance(cases, list):
        raise ValueError("The golden dataset must contain a cases list.")
    if len(cases) != dataset.get("case_count"):
        raise ValueError(
            "Golden dataset case_count does not match the number of cases."
        )

    required_fields = {
        "id",
        "category",
        "question",
        "portfolio_id",
        "expected_route",
        "expected_risk_class",
        "expected_escalation",
        "answer_rubric",
        "required_evidence",
    }
    case_ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Every golden dataset case must be a JSON object.")
        missing_fields = required_fields - case.keys()
        if missing_fields:
            raise ValueError(
                f"Golden dataset case is missing fields: {sorted(missing_fields)}"
            )
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Every golden dataset case must have a non-empty ID.")
        case_ids.append(case_id)

    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Golden dataset case IDs must be unique.")

    actual_category_counts = dict(Counter(case["category"] for case in cases))
    if actual_category_counts != dataset.get("category_counts"):
        raise ValueError(
            "Golden dataset category_counts does not match the cases."
        )

    for field in ("dataset_id", "version", "status", "description"):
        if not dataset.get(field):
            raise ValueError(f"Golden dataset manifest is missing {field}.")

    return dataset


def get_dataset_name(dataset: dict[str, Any]) -> str:
    """Return a stable Langfuse dataset name for this golden dataset version."""
    return f"{dataset['dataset_id']}-v{dataset['version']}"


def ensure_dataset(langfuse: Langfuse, dataset: dict[str, Any]) -> str:
    """Create the versioned dataset only if it does not already exist."""
    dataset_name = get_dataset_name(dataset)
    page = 1

    while True:
        response = langfuse.api.datasets.list(
            page=page,
            limit=DATASET_PAGE_SIZE,
        )
        if any(existing.name == dataset_name for existing in response.data):
            print(f"Dataset '{dataset_name}' already exists.")
            return dataset_name
        if response.meta.total_pages <= page:
            break
        page += 1

    langfuse.create_dataset(
        name=dataset_name,
        description=dataset["description"],
        metadata={
            "dataset_id": dataset["dataset_id"],
            "version": dataset["version"],
            "status": dataset["status"],
            "category_counts": dataset["category_counts"],
        },
    )
    print(f"Created dataset '{dataset_name}'.")
    return dataset_name


def _dataset_item_id(dataset_name: str, case_id: str) -> str:
    """Build a stable, globally unique item ID so Langfuse can upsert reruns."""
    return str(uuid5(NAMESPACE_URL, f"langfuse:{dataset_name}:{case_id}"))


def add_items(
    langfuse: Langfuse,
    dataset_name: str,
    dataset: dict[str, Any],
) -> int:
    """Upsert all golden cases as Langfuse dataset items."""
    version = dataset["version"]
    review_status = dataset["status"]

    for case in dataset["cases"]:
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            id=_dataset_item_id(dataset_name, case["id"]),
            input={
                "question": case["question"],
                "portfolio_id": case["portfolio_id"],
            },
            expected_output={
                "expected_route": case["expected_route"],
                "expected_risk_class": case["expected_risk_class"],
                "expected_escalation": case["expected_escalation"],
                "expected_result": case.get("expected_result"),
                "answer_rubric": case["answer_rubric"],
                "required_evidence": case["required_evidence"],
            },
            metadata={
                "case_id": case["id"],
                "category": case["category"],
                "dataset_version": version,
                "review_status": review_status,
            },
        )

    return len(dataset["cases"])


def upload_dataset(langfuse: Langfuse, dataset: dict[str, Any]) -> int:
    """Ensure the dataset exists and upsert every golden case."""
    dataset_name = ensure_dataset(langfuse, dataset)
    return add_items(langfuse, dataset_name, dataset)


def main() -> None:
    """Upload all cases from the versioned golden dataset."""
    dataset = load_golden_dataset()
    dataset_name = get_dataset_name(dataset)
    langfuse = get_langfuse_client()

    item_count = upload_dataset(langfuse, dataset)
    category_summary = ", ".join(
        f"{category}: {count}"
        for category, count in sorted(dataset["category_counts"].items())
    )
    print(
        f"Upserted {item_count} items into '{dataset_name}' "
        f"({category_summary}; status: {dataset['status']})."
    )


if __name__ == "__main__":
    main()
