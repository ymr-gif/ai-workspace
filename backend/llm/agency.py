import logging

from config import MODELS
from llm.nim import call

logger = logging.getLogger("agency")

_SUGGESTION_PROMPT = """\
User asked: "{user_msg}"
Assistant replied: "{ai_msg}"

Suggest one specific, concrete next action in 12 words or fewer.
Start with a verb. Be specific to the content above.
If nothing useful, respond with exactly: NONE"""

_INSIGHT_PROMPT = """\
Analyze this user's AI assistant data and identify ONE specific insight.

User memory:
{memory}

Recent questions asked:
{recent_topics}

Write a single sentence about a pattern, gap, or opportunity.
Start with "You " or "Your " or "Pattern: ".
If nothing meaningful, respond with exactly: NONE"""


async def generate_proactive_suggestion(user_msg: str, ai_msg: str) -> str | None:
    prompt = _SUGGESTION_PROMPT.format(
        user_msg=user_msg[:150],
        ai_msg=ai_msg[:250],
    )
    try:
        result = await call(
            model=MODELS["llama"],
            messages=[{"role": "user", "content": prompt}],
            request_id="proactive",
            model_params={"max_tokens": 35, "temperature": 0.3},
        )
        text = (result.get("content") or "").strip().strip('"')
        if text and text.upper() != "NONE" and len(text) > 8:
            return text
    except Exception:
        logger.warning("[agency] proactive suggestion failed")
    return None


async def generate_user_insight(user_id: int, memory: str, recent_topics: str) -> str | None:
    prompt = _INSIGHT_PROMPT.format(
        memory=memory[:600],
        recent_topics=recent_topics[:400],
    )
    try:
        result = await call(
            model=MODELS["llama"],
            messages=[{"role": "user", "content": prompt}],
            request_id=f"insight-{user_id}",
            model_params={"max_tokens": 60, "temperature": 0.4},
        )
        text = (result.get("content") or "").strip().strip('"')
        if text and text.upper() != "NONE" and len(text) > 10:
            return text
    except Exception:
        logger.warning("[agency] insight failed user=%s", user_id)
    return None
