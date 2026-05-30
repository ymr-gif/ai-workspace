import logging
import string
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from models import UserBehaviorProfile

logger = logging.getLogger("behavior")

_STOP_WORDS = frozenset({
    "the", "is", "at", "which", "on", "for", "and", "are", "was", "were",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "this", "that", "these", "those", "with", "from", "about", "into",
    "through", "during", "before", "after", "above", "below", "between",
    "such", "each", "both", "few", "more", "most", "other", "some",
    "than", "then", "very", "just", "also", "can", "make", "use", "get",
    "like", "one", "two", "new", "how", "what", "why", "when", "where",
})

_MAX_TOPICS = 50


def detect_recurring_patterns(profile: dict) -> list[str]:
    topics = profile.get("topic_keywords", {})
    return sorted(t for t, c in topics.items() if c >= 3)


def _extract_keywords(message: str) -> list[str]:
    words = message.lower().split()
    result = []
    for w in words:
        w = w.strip(string.punctuation)
        if len(w) > 4 and w not in _STOP_WORDS:
            result.append(w)
        if len(result) >= 10:
            break
    return result


async def update_behavior_profile(
    user_id:    int,
    query_type: str,
    message:    str,
    tool_names: list[str],
    model_used: str,
    db:         AsyncSession,
) -> None:
    row = await db.get(UserBehaviorProfile, user_id)
    if not row:
        row = UserBehaviorProfile(user_id=user_id, profile={})
        db.add(row)
        await db.flush()

    profile = dict(row.profile)

    query_types = profile.setdefault("query_types", {})
    query_types[query_type] = query_types.get(query_type, 0) + 1

    topic_keywords = profile.setdefault("topic_keywords", {})
    for kw in _extract_keywords(message):
        topic_keywords[kw] = topic_keywords.get(kw, 0) + 1
    if len(topic_keywords) > _MAX_TOPICS:
        sorted_kw = sorted(topic_keywords.items(), key=lambda x: -x[1])[:_MAX_TOPICS]
        topic_keywords.clear()
        topic_keywords.update(dict(sorted_kw))

    tools_used = profile.setdefault("tools_used", {})
    for name in tool_names:
        tools_used[name] = tools_used.get(name, 0) + 1

    models_used = profile.setdefault("models_used", {})
    models_used[model_used] = models_used.get(model_used, 0) + 1

    profile["total_messages"] = profile.get("total_messages", 0) + 1

    row.profile = profile
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
