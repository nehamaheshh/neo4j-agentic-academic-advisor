from typing import List, Dict, Any
from src.llm.ollama_client import OllamaClient
from src.agents.planner import Plan
from src.agents.schema_context import SCHEMA


SYSTEM = f"""
You are a QA assistant for a Neo4j-backed course/program graph.

You MUST answer in natural language ONLY.
Do NOT output Cypher. Do NOT output code. Do NOT output JSON.

Use ONLY the provided rows as evidence.
If rows are empty, say you couldn't find it in the graph.

Keep answers concise (3-10 lines).
{SCHEMA}
"""


def _uniq_sorted(items: List[str]) -> List[str]:
    out = []
    seen = set()
    for x in items:
        if not x:
            continue
        if x not in seen:
            seen.add(x)
            out.append(x)
    return sorted(out)


def _format_course_list(rows: List[Dict[str, Any]], code_key: str = "code", title_key: str = "title") -> str:
    # rows like: [{"code":"DMS430","title":"Agentic AI Systems"}, ...]
    items = []
    for r in rows:
        code = r.get(code_key)
        title = r.get(title_key) or ""
        if code:
            items.append((code, title))
    # unique by code
    by_code = {}
    for c, t in items:
        by_code[c] = t
    lines = []
    for c in sorted(by_code.keys()):
        t = by_code[c]
        lines.append(f"- {c}" + (f": {t}" if t else ""))
    return "\n".join(lines)


def _format_program_requirements(rows: List[Dict[str, Any]]) -> str:
    # rows like: [{"type":"Core","code":"DMS401","title":"Applied ML"}, ...]
    core = []
    elective = []
    other = []
    for r in rows:
        typ = (r.get("type") or "").strip()
        code = r.get("code")
        title = r.get("title") or ""
        if not code:
            continue
        item = f"- {code}" + (f": {title}" if title else "")
        if typ.lower() == "core":
            core.append(item)
        elif typ.lower() == "elective":
            elective.append(item)
        else:
            other.append(item)

    parts = []
    if core:
        parts.append("**Core:**\n" + "\n".join(core))
    if elective:
        parts.append("**Electives:**\n" + "\n".join(elective))
    if other:
        parts.append("**Other:**\n" + "\n".join(other))
    return "\n\n".join(parts).strip()


def answer(llm: OllamaClient, plan: Plan, question: str, rows: List[Dict[str, Any]]) -> str:
    intent = (plan.intent or "unknown").strip()

    # ---------- Deterministic (non-LLM) answers for reliability ----------
    if intent == "course_details":
        # rows like: [{"c": {...props...}}]
        if not rows:
            return "I couldn't find that course in the graph."
        c = rows[0].get("c") or rows[0]
        code = c.get("course_code") or (plan.course_codes[0] if plan.course_codes else plan.target_course) or "Unknown"
        title = c.get("title", "")
        level = c.get("level", "")
        credits = c.get("credits", "")
        desc = c.get("description", "")
        out = f"**{code} — {title}**"
        meta = []
        if level:
            meta.append(str(level))
        if credits != "":
            meta.append(f"{credits} credits")
        if meta:
            out += f" ({', '.join(meta)})"
        if desc:
            out += f"\n{desc}"
        return out

    if intent in ("direct_prereqs", "all_prereqs", "next_courses"):
        if not rows:
            # be explicit about which list you couldn't find
            if intent == "next_courses":
                return "I couldn't find any next courses unlocked by that course in the graph."
            return "I couldn't find prerequisites for that course in the graph."
        # Expect rows like: {"code": "...", "title": "..."}
        header = {
            "direct_prereqs": "Direct prerequisites (1-hop):",
            "all_prereqs": "All prerequisites (transitive closure):",
            "next_courses": "Courses unlocked next:",
        }[intent]
        return header + "\n" + _format_course_list(rows)

    if intent == "program_requirements":
        if not rows:
            return "I couldn't find program requirements for that program in the graph."
        return "Program requirements (from the graph):\n\n" + _format_program_requirements(rows)

    if intent == "prereq_path":
        # rows like: {"path_nodes":[{course_code:...}, ...], "hops": N}
        if not rows or "path_nodes" not in rows[0]:
            return "I couldn't find a prerequisite path for that course in the graph."
        nodes = rows[0].get("path_nodes") or []
        codes = [n.get("course_code") for n in nodes if isinstance(n, dict)]
        codes = _uniq_sorted([c for c in codes if c])
        if not codes:
            return "I couldn't format the prerequisite path from the graph results."
        # Try to preserve order if possible (nodes(p) usually comes ordered)
        ordered = [n.get("course_code") for n in nodes if isinstance(n, dict) and n.get("course_code")]
        pretty = " \u2192 ".join(ordered) if ordered else " \u2192 ".join(codes)
        return f"Shortest prerequisite path:\n{pretty}"

    # ---------- LLM fallback for unknown or complex intents ----------
    if not rows:
        return "I couldn't find that in the graph."

    user = (
        f"Question: {question}\n"
        f"Intent: {intent}\n"
        f"Evidence rows: {rows}\n\n"
        "Answer ONLY in natural language."
    )
    return llm.chat(SYSTEM, user, temperature=0.2)
