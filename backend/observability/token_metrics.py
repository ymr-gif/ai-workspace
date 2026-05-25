from prometheus_client import Counter

TOKENS_PROMPT     = Counter("tokens_prompt_total",      "Input tokens by model",            ["model"])
TOKENS_COMPLETION = Counter("tokens_completion_total",  "Output tokens by model",           ["model"])
TOKENS_TOTAL      = Counter("tokens_total",             "Total tokens by model",            ["model"])
COST_USD          = Counter("estimated_cost_usd_total", "Estimated cost in USD by model",   ["model"])


def record_tokens(model: str, prompt: int, completion: int, cost: float) -> None:
    try:
        TOKENS_PROMPT.labels(model=model).inc(prompt)
        TOKENS_COMPLETION.labels(model=model).inc(completion)
        TOKENS_TOTAL.labels(model=model).inc(prompt + completion)
        COST_USD.labels(model=model).inc(cost)
    except Exception:
        pass
