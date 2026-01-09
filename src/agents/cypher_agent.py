import json
from typing import Dict, Any, Optional
from pydantic import BaseModel

from src.llm.ollama_client import OllamaClient
from src.agents.schema_context import SCHEMA
from src.agents.planner import Plan


class CypherOut(BaseModel):
    cypher: str
    params: Dict[str, Any]


# --- Deterministic templates (preferred) ---
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "course_details": {
        "cypher": "MATCH (c:Course {course_code:$code}) RETURN c LIMIT 1",
        "param_map": lambda plan: {"code": (plan.course_codes[0] if plan.course_codes else plan.target_course)},
    },
    "direct_prereqs": {
        "cypher": """
MATCH (pre:Course)-[:PREREQUISITE]->(c:Course {course_code:$code})
RETURN pre.course_code AS code, pre.title AS title
ORDER BY code
LIMIT 200
""".strip(),
        "param_map": lambda plan: {"code": (plan.course_codes[0] if plan.course_codes else plan.target_course)},
    },
    # ✅ Correct for: "What do I need before I can take X?"
    "all_prereqs": {
        "cypher": """
MATCH (pre:Course)-[:PREREQUISITE*1..10]->(c:Course {course_code:$code})
RETURN DISTINCT pre.course_code AS code, pre.title AS title
ORDER BY code
LIMIT 500
""".strip(),
        "param_map": lambda plan: {"code": (plan.course_codes[0] if plan.course_codes else plan.target_course)},
    },
    # "Shortest chain" (one path) — not the full prereq closure
    "prereq_path": {
        "cypher": """
MATCH p=(pre:Course)-[:PREREQUISITE*1..10]->(c:Course {course_code:$code})
RETURN nodes(p) AS path_nodes, length(p) AS hops
ORDER BY hops ASC
LIMIT 1
""".strip(),
        "param_map": lambda plan: {"code": (plan.course_codes[0] if plan.course_codes else plan.target_course)},
    },
    "program_requirements": {
        "cypher": """
MATCH (p:Program {program_id:$pid})-[r:REQUIRES]->(c:Course)
RETURN r.requirement_type AS type, c.course_code AS code, c.title AS title
ORDER BY type, code
LIMIT 500
""".strip(),
        "param_map": lambda plan: {"pid": (plan.program_ids[0] if plan.program_ids else None)},
    },
    "next_courses": {
        "cypher": """
MATCH (completed:Course {course_code:$code})<-[:PREREQUISITE]-(next:Course)
RETURN next.course_code AS code, next.title AS title
ORDER BY code
LIMIT 200
""".strip(),
        "param_map": lambda plan: {"code": (plan.course_codes[0] if plan.course_codes else plan.target_course)},
    },
}


SYSTEM = f"""
You are a Cypher generator for Neo4j.
Return ONLY JSON:
{{
  "cypher": "MATCH ... RETURN ...",
  "params": {{...}}
}}

Rules:
- READ ONLY Cypher only (no CREATE/MERGE/SET/DELETE/CALL/LOAD CSV)
- Use parameters ($code, $pid), never hardcode course codes/program ids
- Prefer LIMIT 200-500 for list outputs
- If the question asks "what do I need before X" prefer returning ALL prerequisites:
  MATCH (pre)-[:PREREQUISITE*1..10]->(c {{course_code:$code}})
  RETURN DISTINCT pre.course_code, pre.title

{SCHEMA}

If you are unsure, return a conservative query that retrieves course details.
"""


def _template_for_intent(intent: str) -> Optional[Dict[str, Any]]:
    return TEMPLATES.get(intent)


def _fill_template(plan: Plan, intent: str) -> CypherOut:
    t = TEMPLATES[intent]
    params = t["param_map"](plan)

    # Defensive defaults
    if params is None:
        params = {}
    # Remove None values (Neo4j driver dislikes them sometimes)
    params = {k: v for k, v in params.items() if v is not None}

    return CypherOut(cypher=t["cypher"], params=params)


def _safe_json_loads(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception:
        return {}


def build_cypher(llm: OllamaClient, plan: Plan, question: str, hint: str = "") -> CypherOut:
    intent = (plan.intent or "unknown").strip()

    # ✅ Always use deterministic templates for these intents (most reliable)
    if intent in ("all_prereqs", "direct_prereqs", "prereq_path", "program_requirements", "next_courses", "course_details"):
        # Ensure required ids exist
        if intent == "program_requirements" and plan.program_ids:
            return _fill_template(plan, intent)
        if intent != "program_requirements" and (plan.course_codes or plan.target_course):
            return _fill_template(plan, intent)

    # --- LLM fallback only if we truly can't template ---
    user = json.dumps(
        {"question": question, "plan": plan.model_dump(), "verifier_hint": hint},
        ensure_ascii=False,
    )
    raw = llm.chat(SYSTEM, user, temperature=0.0, json_only=True)
    data = _safe_json_loads(raw)

    cypher = data.get("cypher") or "MATCH (c:Course) RETURN c LIMIT 1"
    params = data.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    # Patch missing parameters
    if "$code" in cypher and "code" not in params:
        params["code"] = plan.course_codes[0] if plan.course_codes else plan.target_course
    if "$pid" in cypher and "pid" not in params and plan.program_ids:
        params["pid"] = plan.program_ids[0]

    return CypherOut(cypher=cypher, params=params)
