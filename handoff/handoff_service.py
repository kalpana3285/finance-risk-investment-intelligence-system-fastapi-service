import os
import logging
import math
import smtplib
import datetime
import secrets
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from llama_index.core.settings import Settings
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

# SLO thresholds
FAITHFULNESS_THRESHOLD = 0.6
RELEVANCE_THRESHOLD = 0.5
CONFIDENCE_THRESHOLD = 40  # 0-100 scale

def generate_handoff_reference_id(now: Optional[datetime.datetime] = None) -> str:
    """Generate a unique handoff reference ID."""
    now = now or datetime.datetime.now(datetime.UTC)
    return f"HO-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3).upper()}"


def evaluate_score(
    faithfulness: Optional[float],
    relevance: Optional[float],
    user_question: str,
    no_chunks: bool
) -> Dict[str, Any]:
    """
    Determines if the system should escalate based on evaluation scores.
    
    Args:
        faithfulness: Faithfulness score (0-1) or None
        relevance: Relevance score (0-1) or None
        user_question: The user's question
        no_chunks: Whether retrieval returned no context chunks
        
    Returns:
        Dict with "trigger" (bool) and "reason" (str) keys.
    """
    if no_chunks:
        return {"trigger": True, "reason": "retrieval returned no context"}

    if faithfulness is None or relevance is None:
        return {"trigger": True, "reason": "evaluation scores unavailable"}

    if faithfulness < FAITHFULNESS_THRESHOLD:
        return {"trigger": True, "reason": f"faithfulness below {FAITHFULNESS_THRESHOLD}"}

    if relevance < RELEVANCE_THRESHOLD:
        return {"trigger": True, "reason": f"answer relevance below {RELEVANCE_THRESHOLD}"}

    # Keyword fallback (LLM intent classifier will run separately)
    if any(word in user_question.lower() for word in ["human", "agent", "support", "escalate"]):
        return {"trigger": True, "reason": "explicit user request"}

    return {"trigger": False}


def evaluate_confidence_value(confidence: float) -> Dict[str, Any]:
    """Apply the configured handoff threshold to a normalized 0-1 score."""
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("Confidence must be a finite score between 0 and 1.")

    confidence_score = int(confidence * 100)
    if confidence_score < CONFIDENCE_THRESHOLD:
        return {
            "trigger": True,
            "reason": (
                f"LLM confidence below {CONFIDENCE_THRESHOLD} "
                f"(score: {confidence_score})"
            ),
            "confidence": confidence_score,
        }

    return {"trigger": False, "confidence": confidence_score}


async def evaluate_confidence_score(answer: str) -> Dict[str, Any]:
    """
    Evaluate LLM confidence score for the generated answer and determine if handoff should be triggered.
    
    Args:
        answer: The generated answer to evaluate
        
    Returns:
        Dict with "trigger" (bool), "reason" (str), and "confidence" (int) keys.
        Confidence score is an integer between 0-100 (defaults to 50 if parsing fails).
        If confidence is below threshold, trigger will be True.
    """
    llm = Settings.llm
    if llm is None:
        raise ValueError("LLM not initialized")
    
    confidence_prompt = f"Rate confidence 0–100.\nAnswer: {answer}"
    confidence_resp = await llm.acomplete(confidence_prompt)
    confidence_score = int("".join(filter(str.isdigit, confidence_resp.text)) or 50)
    return evaluate_confidence_value(confidence_score / 100)


async def evaluate_explicit_user_request(message: str) -> Dict[str, Any]:
    """
    LLM-based classifier for explicit user request or frustration.
    
    Returns:
        Dict with "trigger" (bool) and "reason" (str) keys.
        If trigger is True, reason will be "LLM classified explicit handoff request".
    """
    llm = Settings.llm
    if llm is None:
        raise ValueError("LLM not initialized")

    prompt = f"""
The user might be asking for human help.
Return only YES or NO.

Message: "{message}"
"""

    resp = await llm.acomplete(prompt)
    is_explicit_request = "YES" in resp.text.upper()
    
    if is_explicit_request:
        return {"trigger": True, "reason": "LLM classified explicit handoff request"}
    
    return {"trigger": False}

def send_handoff_email(context: Dict[str, Any]):
    """Send CLEAN, Sprint Master–aligned human handoff email."""
    load_dotenv()
    smtp_host = os.getenv("SMTP_HOST")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("APPLICATION_EMAIL")
    email_to = os.getenv("SUPPORT_EMAIL")
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        logger.error("SMTP_PORT must be an integer. Cannot send handoff email.")
        return

    if not all([smtp_host, smtp_username, smtp_password, email_from, email_to]):
        logger.warning("Email settings missing. Cannot send handoff email.")
        return

    subject = f"[HUMAN HANDOFF] Ref {context['reference_id']} – {context['trigger_reason']}"

    body = f"""
A human handoff has been triggered.

Reference ID: {context['reference_id']}
Trace ID: {context['trace_id']}
Timestamp: {context['timestamp_utc']}
Priority: {context['priority']}

Reason for Handoff:
{context['trigger_reason']}

User Metadata:
Email: {context['user_metadata'].get('email')}
Session ID: {context['session_id']}

------------------------------------------------------------
User Query History:
------------------------------------------------------------
{context['query_history']}

------------------------------------------------------------
Generated Answer:
------------------------------------------------------------
{context['generated_answer']}

------------------------------------------------------------
Evaluation Scores:
------------------------------------------------------------
Faithfulness (0-1): {context['evaluation_scores']['faithfulness']}
Relevance (0-1): {context['evaluation_scores']['relevance']}
LLM Confidence (0-100): {context['evaluation_scores']['confidence']}

------------------------------------------------------------
Retrieved Chunks (Full Content):
------------------------------------------------------------
{context['retrieved_chunks']}

------------------------------------------------------------
Conversation Flow:
------------------------------------------------------------
{context['conversation_flow']}
"""

    msg = MIMEText(body)
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = subject

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(email_from, email_to, msg.as_string())
        logger.info("Human handoff email sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send handoff email: {e}")