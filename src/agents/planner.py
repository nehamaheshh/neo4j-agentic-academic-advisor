import json, re
from pydantic import BaseModel
from typing import List, Literal, Optional
from src.llm.ollama_client import OllamaClient
from src.agents.schema_context import SCHEMA

Intent = Literal[
    "course_details",
    "direct_prereqs",
    "all_prereqs",
    "prereq_path",
    "program_requirements",
    "eligibility_check",
    "next_courses",
    "unknown"
]


COURSE_RE = re.compile(r"\b[A-Z]{2,4}\d{3}\b")
PROG_RE = re.compile(r"\b(MSDS|BSCS|BASTAT)\b")

class Plan(BaseModel):
    intent: Intent
    course_codes: List[str]
    program_ids: List[str]
    need_multihop: bool
    notes: str
    # new fields for eligibility checks
    target_course: Optional[str] = None
    completed_courses: List[str] = []

SYSTEM = f"""
You are a planner for a Neo4j graph QA assistant.

Return ONLY JSON matching:
{{
  "intent": "course_details|direct_prereqs|all_prereqs|prereq_path|program_requirements|eligibility_check|next_courses|unknown",
  "course_codes": ["..."],
  "program_ids": ["..."],
  "need_multihop": true/false,
  "notes": "short",
  "target_course": "COURSECODE or null",
  "completed_courses": ["COURSECODE", ...]
}}

CRITICAL INTENT ROUTING (follow exactly):
- If user asks:
  - "What do I need before I can take X?"
  - "What are ALL prerequisites for X?"
  - "What prerequisites are required for X?"
  => intent = "all_prereqs" (return full prerequisite closure)

- If user asks:
  - "Show the shortest path to X"
  - "Give one prerequisite chain to reach X"
  => intent = "prereq_path" (return a single shortest chain)

- If user asks:
  - "What are the direct prerequisites for X?"
  => intent = "direct_prereqs" (one-hop prereqs only)

- If user asks:
  - "Can I take X if I completed Y, Z?"
  => intent = "eligibility_check"
     target_course = X, completed_courses = [Y, Z]

Examples:
Q: "What do I need before I can take DMS440?"
A: {{"intent":"all_prereqs","course_codes":["DMS440"],"program_ids":[],"need_multihop":true,"notes":"Return all prerequisites (closure).","target_course":"DMS440","completed_courses":[]}}

Q: "Show the shortest prerequisite chain to DMS440"
A: {{"intent":"prereq_path","course_codes":["DMS440"],"program_ids":[],"need_multihop":true,"notes":"Return shortest chain.","target_course":"DMS440","completed_courses":[]}}

Use regex candidates provided in the user message to fill course_codes/program_ids.

{SCHEMA}
"""


def _regex_extract(question: str):
    courses = list(dict.fromkeys(COURSE_RE.findall(question.upper())))
    progs = list(dict.fromkeys(PROG_RE.findall(question.upper())))
    return courses, progs

def make_plan(llm: OllamaClient, question: str) -> Plan:
    # Provide regex candidates to improve reliability
    courses, progs = _regex_extract(question)
    user = json.dumps({"question": question, "regex_course_codes": courses, "regex_program_ids": progs})
    raw = llm.chat(SYSTEM, user, temperature=0.0, json_only=True)
    data = json.loads(raw)

    # ---- Robust defaults (LLMs sometimes output null) ----
    if data.get("notes") is None:
        data["notes"] = ""
    if data.get("course_codes") is None:
        data["course_codes"] = []
    if data.get("program_ids") is None:
        data["program_ids"] = []
    if data.get("completed_courses") is None:
        data["completed_courses"] = []
    if data.get("need_multihop") is None:
        data["need_multihop"] = False

    return Plan(**data)

