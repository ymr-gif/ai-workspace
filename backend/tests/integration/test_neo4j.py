"""Infra: Neo4j reachability + graph-memory index presence. Marker: infra."""
import pytest

pytestmark = pytest.mark.infra


def test_round_trip_query(neo4j_conn):
    with neo4j_conn.session() as s:
        assert s.run("RETURN 1 AS n").single()["n"] == 1


def test_entity_indexes_present(neo4j_conn):
    """Startup creates the (user_id,name) constraint + fulltext entity_name_ft."""
    with neo4j_conn.session() as s:
        names = {r["name"] for r in s.run("SHOW INDEXES YIELD name RETURN name")}
    # entity_name_ft is created by init_neo4j(); its absence means startup index
    # creation did not run against this instance.
    assert any("entity" in n.lower() or "ft" in n.lower() for n in names), f"no entity indexes: {names}"
