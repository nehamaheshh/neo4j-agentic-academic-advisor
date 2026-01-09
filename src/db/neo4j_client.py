from neo4j import GraphDatabase
from typing import Any, Dict, List, Optional

READ_ONLY_PREFIXES = ("MATCH", "WITH", "RETURN", "UNWIND")

def _is_read_only_cypher(query: str) -> bool:
    q = query.strip().upper()
    # very simple guardrails
    blocked = ["CREATE", "MERGE", "SET", "DELETE", "DROP", "CALL", "LOAD CSV"]
    if any(b in q for b in blocked):
        return False
    return q.startswith(READ_ONLY_PREFIXES)

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_read(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not _is_read_only_cypher(query):
            raise ValueError("Blocked non-read-only Cypher for safety.")
        params = params or {}
        with self.driver.session() as session:
            res = session.run(query, params)
            return [r.data() for r in res]

    def run_write(self, query: str, params: Optional[Dict[str, Any]] = None) -> None:
        params = params or {}
        with self.driver.session() as session:
            session.run(query, params)
