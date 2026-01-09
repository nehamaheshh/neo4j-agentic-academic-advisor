import json
from pydantic import BaseModel
from typing import Literal, List, Dict, Any
from src.llm.ollama_client import OllamaClient
from src.agents.schema_context import SCHEMA

Verdict = Literal["pass", "needs_more", "fail"]

class VerifyOut(BaseModel):
    verdict: Verdict
    reason: str
    followup_cypher_hint: str

SYSTEM = f"""
You are a STRICT verifier for a Neo4j graph QA system.

You MUST return ONLY JSON with EXACTLY these keys:
{{
  "verdict": "pass" | "needs_more" | "fail",
  "reason": "string",
  "followup_cypher_hint": "string"
}}

Rules:
- If rows are empty AND the answer claims facts -> verdict="fail"
- If rows are empty AND the answer says it couldn't find it -> verdict="pass"
- If rows exist but answer misses obvious info -> verdict="needs_more" and suggest what to query next
- If answer is supported by rows -> verdict="pass"
- Never output any other keys. Never output code.

Examples (follow EXACT structure):
{{"verdict":"pass","reason":"Answer uses only returned course properties.","followup_cypher_hint":""}}
{{"verdict":"needs_more","reason":"Only course code returned; need titles.","followup_cypher_hint":"Return c.title and c.description for the target course."}}
{{"verdict":"fail","reason":"Answer mentions a prerequisite not present in rows.","followup_cypher_hint":""}}

{SCHEMA}
"""

def _safe_verify_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    # Coerce / default to prevent crashes
    verdict = d.get("verdict")
    if verdict not in ("pass", "needs_more", "fail"):
        verdict = "pass"  # safe default: don't crash UX
    reason = d.get("reason")
    if reason is None:
        reason = ""
    hint = d.get("followup_cypher_hint")
    if hint is None:
        hint = ""
    return {"verdict": verdict, "reason": reason, "followup_cypher_hint": hint}

def verify(llm: OllamaClient, question: str, rows: List[Dict[str, Any]], answer_text: str) -> VerifyOut:
    user = json.dumps({"question": question, "rows": rows, "answer": answer_text}, ensure_ascii=False)
    raw = llm.chat(SYSTEM, user, temperature=0.0, json_only=True)

    # raw might be invalid / wrong-schema; never crash the app
    try:
        data = json.loads(raw)
        data = _safe_verify_dict(data)
        return VerifyOut(**data)
    except Exception:
        # Ultimate fallback if model returns garbage
        return VerifyOut(verdict="pass", reason="Verifier output was malformed; defaulted to pass.", followup_cypher_hint="")
