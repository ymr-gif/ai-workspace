# HANDOFF
- Updated: 2026-05-28
- Status: done
- Archive: `HANDOFF_ARCHIVE.md` (completed features; see Archive rules in root CLAUDE.md)

---

## History
| Date | Feature | Notes |
|------|---------|-------|
| 2026-05-28 | Re-embed + Graph Memory | All stages complete; committed b972e66 |
| 2026-05-28 | Graph query_context fulltext index | Added entity_name_ft index + swapped CONTAINS to fulltext query |
| 2026-05-28 | Graph limit + score threshold | limit 8→50; min_score=0.5 filter in Cypher; query_by_term forwards min_score |
