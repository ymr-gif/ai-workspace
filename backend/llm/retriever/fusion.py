_RRF_K   = 60
_FETCH_N = 20


def _weighted_merge(
    vector_rows: list[tuple],
    bm25_rows:   list[tuple],
    top_k:       int,
    alpha:       float = 0.5,
) -> list[dict]:
    dense_scores:  dict = {}
    sparse_scores: dict = {}
    contents:      dict = {}
    source_ids:    dict = {}

    for rid, src_id, content, raw in vector_rows:
        dense_scores[rid]  = raw
        contents[rid]      = content
        source_ids[rid]    = src_id

    for rid, src_id, content, raw in bm25_rows:
        sparse_scores[rid] = raw
        contents.setdefault(rid, content)
        source_ids.setdefault(rid, src_id)

    max_dense  = max(dense_scores.values())  if dense_scores  else 1.0
    max_sparse = max(sparse_scores.values()) if sparse_scores else 1.0

    all_ids    = set(dense_scores) | set(sparse_scores)
    result = []
    for i in all_ids:
        d     = dense_scores.get(i, 0.0)  / max_dense  if max_dense  > 0 else 0.0
        s     = sparse_scores.get(i, 0.0) / max_sparse if max_sparse > 0 else 0.0
        final = alpha * d + (1.0 - alpha) * s
        result.append({
            "chunk_id":      i,
            "source_id":     source_ids.get(i),
            "content":       contents[i],
            "dense_score":   round(d, 6),
            "sparse_score":  round(s, 6),
            "final_score":   round(final, 6),
            "retrieval_type": "weighted",
        })

    result.sort(key=lambda x: -x["final_score"])
    return result[:top_k]


def _rrf_merge(
    vector_rows: list[tuple],
    bm25_rows:   list[tuple],
    top_k:       int,
) -> list[dict]:
    dense:      dict = {}
    sparse:     dict = {}
    contents:   dict = {}
    source_ids: dict = {}
    for rank, (rid, src_id, content) in enumerate(vector_rows):
        dense[rid]      = 1.0 / (_RRF_K + rank + 1)
        contents[rid]   = content
        source_ids[rid] = src_id
    for rank, (rid, src_id, content) in enumerate(bm25_rows):
        sparse[rid] = 1.0 / (_RRF_K + rank + 1)
        contents[rid] = content
        source_ids.setdefault(rid, src_id)
    all_ids    = set(dense) | set(sparse)
    sorted_ids = sorted(all_ids, key=lambda x: -(dense.get(x, 0.0) + sparse.get(x, 0.0)))
    result = []
    for i in sorted_ids[:top_k]:
        d   = round(dense.get(i, 0.0), 6)
        s   = round(sparse.get(i, 0.0), 6)
        rtype = "+".join(sorted(filter(None, ["bm25" if s else "", "vector" if d else ""])))
        result.append({
            "chunk_id":      i,
            "source_id":     source_ids.get(i),
            "content":       contents[i],
            "dense_score":   d,
            "sparse_score":  s,
            "final_score":   round(d + s, 6),
            "retrieval_type": rtype,
        })
    return result
