"""Local input validation and PII sanitization for query results."""

from __future__ import annotations

import importlib.util
import logging
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents.control_plane import OrchestrationResult

logger = logging.getLogger(__name__)

_PII_PLACEHOLDER = re.compile(r"\s*<[A-Z][A-Z0-9_]*>\s*")
_INTERNAL_DOCUMENT_REFERENCE = re.compile(
    r"\bFRIIS[-_]DOC[-_]\d+(?:\s*<[A-Z][A-Z0-9_]*>)?\s*(?:\.\d+)?\b",
    re.IGNORECASE,
)

MAX_QUERY_LENGTH = 4000
PII_REDACTION_LIMITATION = (
    "Sensitive personal information was redacted from the response, citations, "
    "or escalation details."
)
PII_ENTITIES = (
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "CREDIT_CARD",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "PERSON",
    "LOCATION",
    "DATE_TIME",
)


@dataclass(frozen=True)
class InputDecision:
    allowed: bool
    reason: str | None = None


@dataclass(frozen=True)
class OutputDecision:
    sanitized_text: str
    pii_detected: bool


class GuardrailsConfigurationError(RuntimeError):
    """Raised when the local PII validator cannot be configured."""


class GuardrailsValidationError(RuntimeError):
    """Raised when the local PII validator returns an invalid result."""


class GuardrailsValidator:
    """Validate question shape and redact PII from user-visible query results."""

    def __init__(
        self,
        *,
        pii_scanner: Callable[[str], str] | None = None,
    ) -> None:
        self._pii_scanner = pii_scanner

    @staticmethod
    def validate_input(text: str) -> InputDecision:
        if not isinstance(text, str) or not text.strip():
            return InputDecision(allowed=False, reason="Query cannot be empty.")
        if len(text) > MAX_QUERY_LENGTH:
            return InputDecision(
                allowed=False,
                reason=f"Query cannot exceed {MAX_QUERY_LENGTH} characters.",
            )
        return InputDecision(allowed=True)

    def validate_output(self, text: str) -> OutputDecision:
        sanitized = self._get_pii_scanner()(text)
        if not isinstance(sanitized, str):
            raise GuardrailsValidationError(
                "The local PII validator returned a non-text result."
            )
        return OutputDecision(
            sanitized_text=sanitized,
            pii_detected=sanitized != text,
        )

    def sanitize_result(
        self, result: OrchestrationResult
    ) -> tuple[OrchestrationResult, bool]:
        pii_detected = False

        def sanitize(text: str | None) -> str | None:
            nonlocal pii_detected
            if text is None:
                return None
            decision = self.validate_output(text)
            pii_detected = pii_detected or decision.pii_detected
            # The PII scanner may emit entity labels such as
            # ``<US_DRIVER_LICENSE>``. Those are internal redaction markers,
            # not useful user-facing text. Source catalog IDs are likewise
            # implementation metadata and should not appear in the answer.
            clean_text = _PII_PLACEHOLDER.sub(" ", decision.sanitized_text)
            clean_text = _INTERNAL_DOCUMENT_REFERENCE.sub("", clean_text)
            clean_text = re.sub(r"\(\s*\|\s*", "(", clean_text)
            clean_text = re.sub(r"\s*\|\s*\)", ")", clean_text)
            clean_text = re.sub(r"\s+([,.;:])", r"\1", clean_text)
            clean_text = re.sub(r"\s{2,}", " ", clean_text).strip()
            return clean_text

        citations = tuple(
            citation.model_copy(
                update={
                    "source_title": sanitize(citation.source_title),
                    "excerpt": sanitize(citation.excerpt),
                }
            )
            for citation in result.citations
        )
        limitations = tuple(
            sanitize(limitation) or "" for limitation in result.limitations
        )
        escalation = result.escalation
        if escalation is not None:
            escalation = escalation.model_copy(
                update={
                    "reason": sanitize(escalation.reason) or "",
                    "evidence": tuple(
                        evidence.model_copy(
                            update={
                                "source_title": sanitize(evidence.source_title),
                                "excerpt": sanitize(evidence.excerpt),
                            }
                        )
                        for evidence in escalation.evidence
                    ),
                    "attempted_steps": tuple(
                        sanitize(step) or "" for step in escalation.attempted_steps
                    ),
                    "data_gaps": tuple(
                        sanitize(gap) or "" for gap in escalation.data_gaps
                    ),
                    "requested_review": sanitize(escalation.requested_review) or "",
                }
            )

        if pii_detected and PII_REDACTION_LIMITATION not in limitations:
            limitations += (PII_REDACTION_LIMITATION,)
        sanitized_result = result.model_copy(
            update={
                "answer": sanitize(result.answer),
                "citations": citations,
                "limitations": limitations,
                "clarification_question": sanitize(result.clarification_question),
                "escalation": escalation,
            }
        )
        return sanitized_result, pii_detected

    def _get_pii_scanner(self) -> Callable[[str], str]:
        if self._pii_scanner is not None:
            return self._pii_scanner

        if importlib.util.find_spec("en_core_web_lg") is None:
            logger.warning(
                "en_core_web_lg is not installed; using local regex-based PII "
                "recognizers without named-entity recognition such as PERSON "
                "and LOCATION detection."
            )
            self._pii_scanner = self._create_regex_only_scanner()
            return self._pii_scanner

        self._pii_scanner = self._create_guardrails_scanner()
        return self._pii_scanner

    def _create_guardrails_scanner(self) -> Callable[[str], str]:
        try:
            from guardrails import Guard
        except ImportError as exc:
            raise GuardrailsConfigurationError(
                "Guardrails AI is required to sanitize query output."
            ) from exc

        try:
            from guardrails_ai.detect_pii import DetectPII
        except ImportError:
            try:
                from guardrails.hub import DetectPII
            except ImportError as exc:
                raise GuardrailsConfigurationError(
                    "The Guardrails DetectPII validator is required."
                ) from exc

        pii_guard = Guard().use(
            DetectPII(pii_entities=list(PII_ENTITIES), on_fail="fix")
        )

        def scan(text: str) -> str:
            result = pii_guard.validate(text)
            sanitized = result.validated_output
            if sanitized is None:
                return text
            if not isinstance(sanitized, str):
                raise GuardrailsValidationError(
                    "The local PII validator returned a non-text result."
                )
            return sanitized

        return scan

    @staticmethod
    def _create_regex_only_scanner() -> Callable[[str], str]:
        try:
            import spacy
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngine
            from presidio_anonymizer import AnonymizerEngine
        except ImportError as exc:
            raise GuardrailsConfigurationError(
                "Presidio is required for local PII sanitization."
            ) from exc

        class RegexOnlyNlpEngine(NlpEngine):
            def __init__(self) -> None:
                self._nlp = spacy.blank("en")

            def load(self) -> None:
                return None

            def is_loaded(self) -> bool:
                return True

            def process_text(self, text: str, language: str) -> NlpArtifacts:
                doc = self._nlp(text)
                return NlpArtifacts(
                    entities=list(doc.ents),
                    tokens=doc,
                    tokens_indices=[token.idx for token in doc],
                    lemmas=[token.text for token in doc],
                    nlp_engine=self,
                    language=language,
                )

            def process_batch(
                self,
                texts: Iterable[str],
                language: str,
                batch_size: int = 1,
                n_process: int = 1,
                **kwargs: Any,
            ) -> Iterator[tuple[str, NlpArtifacts]]:
                for text in texts:
                    yield text, self.process_text(text, language)

            def is_stopword(self, word: str, language: str) -> bool:
                return word.lower() in self._nlp.Defaults.stop_words

            def is_punct(self, word: str, language: str) -> bool:
                return bool(word) and all(not character.isalnum() for character in word)

            def get_supported_entities(self) -> list[str]:
                return []

            def get_supported_languages(self) -> list[str]:
                return ["en"]

        analyzer = AnalyzerEngine(nlp_engine=RegexOnlyNlpEngine())
        anonymizer = AnonymizerEngine()

        def scan(text: str) -> str:
            analyzer_results = analyzer.analyze(
                text=text,
                entities=list(PII_ENTITIES),
                language="en",
            )
            return anonymizer.anonymize(
                text=text,
                analyzer_results=analyzer_results,
            ).text

        return scan
