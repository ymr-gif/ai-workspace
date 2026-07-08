"""Reasoning-loop tests (Dimension 3) — grounding confidence + intent. No live NIM."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from api.chat.stream import _compute_grounding
from llm.router import classify_intent, _is_ack


def _prov(dense, retrieval_type="weighted", source_id="s"):
    return {"dense_score": dense, "sparse_score": 0.1, "final_score": 0.5,
            "retrieval_type": retrieval_type, "source_id": source_id}


class TestGroundingConfidence:
    def test_empty_provenance_is_none(self):
        g = _compute_grounding([], top_k=5)
        assert g["level"] == "none"
        assert g["score"] is None
        assert g["sources"] == []

    def test_high_grounding(self):
        prov = [_prov(0.9), _prov(0.88), _prov(0.85), _prov(0.82), _prov(0.80)]
        g = _compute_grounding(prov, top_k=5)
        assert g["level"] == "high"
        assert g["score"] >= 70

    def test_medium_grounding(self):
        # mid similarity, partial coverage
        prov = [_prov(0.55), _prov(0.5)]
        g = _compute_grounding(prov, top_k=5)
        assert g["level"] == "medium"
        assert 40 <= g["score"] < 70

    def test_low_grounding(self):
        prov = [_prov(0.15)]
        g = _compute_grounding(prov, top_k=5)
        assert g["level"] == "low"
        assert g["score"] < 40

    def test_ignores_final_score_cross_mode_skew(self):
        # RRF final_scores are tiny (~0.016) vs weighted (~1.0); confidence must
        # NOT collapse just because fusion mode changed. Same dense → same score.
        weighted = [_prov(0.8, "weighted")]
        weighted[0]["final_score"] = 1.6
        rrf = [_prov(0.8, "rrf")]
        rrf[0]["final_score"] = 0.016
        assert _compute_grounding(weighted, 5)["score"] == _compute_grounding(rrf, 5)["score"]

    def test_coverage_lifts_score(self):
        # full result set scores higher than a single hit at the same similarity
        one  = _compute_grounding([_prov(0.6)], top_k=5)
        many = _compute_grounding([_prov(0.6)] * 5, top_k=5)
        assert many["score"] > one["score"]

    def test_sources_capped_to_top_k(self):
        g = _compute_grounding([_prov(0.5)] * 10, top_k=3)
        assert len(g["sources"]) == 3


class TestIntentKeyword:
    def test_task_phrases(self):
        for m in ("create a file for me", "fix this bug", "delete the old rows",
                  "schedule a weekly report", "implement the parser"):
            assert classify_intent(m) == "task", m

    def test_exploration_phrases(self):
        for m in ("show me everything about my files", "what do you know about me",
                  "brainstorm some ideas", "give me some options"):
            assert classify_intent(m) == "exploration", m

    def test_question_default(self):
        assert classify_intent("what is the capital of France") == ""

    def test_conflicting_is_ambiguous(self):
        # both a task verb and an exploration phrase present
        assert classify_intent("brainstorm and create a plan") == "ambiguous"


class TestAckDetector:
    """C2 — ack fast-path (short-circuit only). Positives must qualify without an
    LLM call; anything with an out-of-set token / '?' / digit / >6 tokens must NOT
    (it falls through to the classifier, which owns the real decision)."""

    POSITIVES = [
        "ok", "okay", "thanks", "thank you", "thankyou",
        "okay thankyou, thats all", "that's all thanks", "got it",
        "cool, thanks", "perfect thank you", "goodbye", "bye",
        "great, that's all", "nice, thanks man", "good day",
        "yep", "sure",
    ]
    NEGATIVES = [
        "thanks, but the formula is wrong",   # style/content pushback → task
        "ok how about arrays?",               # question (has '?')
        "thanks for the 3 examples",          # has a digit
        "okay so explain the next part",      # out-of-set tokens
        "thank you for building the parser",  # substantive, out-of-set tokens
        "is that all?",                       # question
        "ok ok ok ok ok ok ok",               # >6 tokens
        "",                                   # empty
    ]

    def test_positives_qualify(self):
        for m in self.POSITIVES:
            assert _is_ack(m) is True, m

    def test_negatives_do_not_qualify(self):
        for m in self.NEGATIVES:
            assert _is_ack(m) is False, m

    def test_positives_classify_closing(self):
        for m in self.POSITIVES:
            assert classify_intent(m) == "closing", m

    def test_thanks_but_wrong_is_not_closing(self):
        # explicit correction turn must NOT be treated as a goodbye
        assert classify_intent("thanks, but the formula is wrong") != "closing"
