from typing import Dict, List, Tuple
from src.db.neo4j_client import Neo4jClient

PREREQS_ALL = """
MATCH (pre:Course)-[:PREREQUISITE*1..6]->(target:Course {course_code:$code})
RETURN DISTINCT pre.course_code AS code, pre.title AS title
ORDER BY code
"""

def check_eligibility(
    neo: Neo4jClient,
    target: str,
    completed: List[str]
) -> Tuple[bool, List[Dict[str, str]]]:
    rows = neo.run_read(PREREQS_ALL, {"code": target})
    prereq_codes = {r["code"] for r in rows}
    completed_set = set(completed)
    missing_codes = sorted(list(prereq_codes - completed_set))

    missing = [{"code": r["code"], "title": r.get("title", "")} for r in rows if r["code"] in missing_codes]
    eligible = (len(missing) == 0)
    return eligible, missing
