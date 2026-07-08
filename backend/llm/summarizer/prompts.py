_NO_UPDATE = "NO_UPDATE"

_MEMORY_SYSTEM = """\
You maintain a compact memory sheet for a user. Output ONLY key:value pairs grouped under five headers.
Every word must carry information — no filler, no sentences, no prose.

Headers (omit if empty):
[USER]       — name, role, expertise level, background
[STACK]      — languages, frameworks, tools, infra actively used
[PROJECT]    — what they are building, decisions made, constraints, current state
[CORRECTIONS]— errors AI made that were corrected; preferences user had to repeat
[PATTERNS]   — recurring topics, working style, what they care about

Rules:
- Max 500 words total
- Format each line as: key: value
- Remove anything contradicted by newer info
- Be specific — "Python 3.11 + FastAPI async" not "Python backend"
- Style/pacing feedback is a CORRECTION, not a trait. When the user gives an
  imperative about HOW you reply ("stop doing X", "keep it short", "don't give
  unsolicited full walkthroughs", "i said it's okay / that's all"), record it under
  [CORRECTIONS] AND update or DELETE any [PATTERNS]/[USER]/current-state line it
  contradicts (e.g. remove "working style: step-by-step" if they told you to stop).
- Never promote a one-time request ("explain this step by step just now") into a
  permanent trait — a single ask is not a working style.
- On conflict between an existing trait and newer user feedback, RECENCY WINS:
  keep the newer signal, drop the stale one.
- If nothing new to add: reply exactly NO_UPDATE\
"""

_COMPACT_SYSTEM = """\
Review and compact this user memory sheet. Remove:
- Duplicate or overlapping facts
- Stale or superseded information
- Low-value details (transient states, trivial observations)

Keep ONLY:
- Active decisions and their rationale
- Architecture and tech stack choices currently in use
- User preferences and corrections
- Active project status
- Recurring patterns and working style

Output ONLY the compacted key:value pairs under the same five headers:
[USER] [STACK] [PROJECT] [CORRECTIONS] [PATTERNS]

Rules:
- Max 500 words total
- Format each line as: key: value
- Merge related facts, remove redundant entries
- Every word must carry information
- If no meaningful compaction possible: reply exactly NO_UPDATE\
"""

_COMPRESS_SYSTEM = """\
Compress this conversation excerpt into a dense factual summary.
Focus on: decisions made, problems solved, code written, errors fixed, context established.
Output bullet points or key:value pairs. Max 200 words. No filler, no pleasantries.\
"""

_PROJECT_SYSTEM = """\
You maintain a project-level state summary across multiple conversations.
Output ONLY key:value pairs grouped under four headers.
Every word must carry information — no prose, no filler.

Headers (omit if empty):
[GOALS]   — what is being built, current objectives, milestones
[ARCH]    — architecture decisions, tech stack choices, patterns adopted
[STATUS]  — what works, what's broken, current progress
[PENDING] — known issues, next steps, open questions, blockers

Rules:
- Max 300 words total
- Format each line as: key: value
- Remove anything contradicted by newer info
- If nothing new: reply exactly NO_UPDATE\
"""
