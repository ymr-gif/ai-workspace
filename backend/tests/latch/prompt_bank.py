"""Band-tagged example prompts for connector-intent latch data collection.

The agents' job is to reproduce the HARD bands the existing eval sets lack — connector-adjacent
vagueness and task-imperatives (the real over-fire source), terse-but-real, and ties — NOT to
spam obvious positives. Weight traffic toward none_intent + weak_real + tie. Vary phrasing
(identical messages cache-hit and skip the latch).

Shape, not script: extend these, randomize order, and interleave with multi-turn WARM sessions
(latch a connector on a clear turn, then send an unrelated later turn on the same conv_id) so
output C has both cold and warm rows.
"""

# band -> list of prompts. `positive`/`weak_real` should be sent with the matching --connector.
PROMPTS = {
    # clear single-connector intent — anchors, keep a minority of traffic
    "positive": {
        "drive":    ["what files do I have in my drive", "open my budget document",
                     "search my google drive for the contract", "list the files in my drive"],
        "calendar": ["what's on my calendar today", "do I have meetings this week",
                     "schedule a call for tomorrow at 3pm", "am I free friday afternoon"],
        "gmail":    ["check my email", "any unread messages", "find the email from the bank",
                     "search my inbox for the invoice"],
    },

    # terse but GENUINE — Band 3; send with the connector the user actually meant
    "weak_real": {
        "drive":    ["get that document", "pull it up", "find that file", "open it"],
        "calendar": ["what's next", "anything tomorrow", "move it to 4", "cancel that"],
        "gmail":    ["any new mail", "read the latest", "reply to that one", "search for it"],
    },

    # Band 1 — connector-ADJACENT vagueness + task-imperatives. THE over-fire source.
    # No real connector intent; the right answer is to NOT latch (or ask "which X?").
    "none_intent": [
        "find my things", "check my stuff", "look that up", "where is it",
        "show me what I have", "can you find it", "i need that thing from earlier",
        "help me debug this function", "fix this error", "write a python script for me",
        "summarize this paragraph", "explain how this works", "what should I do next",
        "organize my work", "remind me about the project", "what was that called again",
    ],

    # Band 2 — multi-connector (rare in the wild; hand-curated). Margin lives here.
    "tie": [
        "what's in my files and my email",
        "check my calendar and my inbox",
        "find the document and the related emails",
        "anything in drive or gmail about the budget",
        "my schedule and any messages about it",
    ],

    # easy negatives — cheap anchors, keep a minority
    "easy_neg": [
        "hello", "hi there", "thanks", "ok cool", "good morning",
        "how are you", "what's the weather like", "tell me a joke",
        "what is 2 + 2", "who won the world cup",
    ],
}
