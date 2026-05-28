POLICY_MAP = {
    "factual":    {"fusion_mode": "weighted", "alpha": 0.7, "k_dense": 20, "k_sparse": 20, "top_k": 5},
    "relational": {"fusion_mode": "rrf",      "alpha": 0.5, "k_dense": 20, "k_sparse": 20, "top_k": 8, "use_graph": True},
    "temporal":   {"fusion_mode": "rrf",      "alpha": 0.5, "k_dense": 20, "k_sparse": 10, "top_k": 6},
    "broad":      {"fusion_mode": "weighted", "alpha": 0.3, "k_dense": 5,  "k_sparse": 20, "top_k": 3},
}


def get_policy(query_type: str) -> dict:
    return POLICY_MAP.get(query_type, POLICY_MAP["factual"]).copy()


def apply_policy(query_type: str, **overrides) -> dict:
    config = get_policy(query_type)
    config.update(overrides)
    return config
