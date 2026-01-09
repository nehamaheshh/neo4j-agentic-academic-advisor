import sys
from pathlib import Path

# Add project root to PYTHONPATH for Streamlit
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.db.neo4j_client import Neo4jClient
from src.llm.ollama_client import OllamaClient
from src.agents.planner import make_plan
from src.agents.cypher_agent import build_cypher
from src.agents.answer_agent import answer as answer_fn
from src.agents.verifier import verify as verify_fn
from src.rag.eligibility import check_eligibility
from src.rag.formatters import extract_shortest_path, format_path_nodes

load_dotenv()

@st.cache_resource
def get_clients():
    llm = OllamaClient(os.environ["OLLAMA_BASE_URL"], os.environ["OLLAMA_MODEL"])
    neo = Neo4jClient(os.environ["NEO4J_URI"], os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
    return llm, neo

def run_pipeline(llm, neo, question: str):
    plan = make_plan(llm, question)

    # Eligibility shortcut
    if plan.intent == "eligibility_check" and plan.target_course:
        eligible, missing = check_eligibility(neo, plan.target_course, plan.completed_courses)
        if eligible:
            ans = f"Yes — you appear eligible to take {plan.target_course}. (All prerequisites are satisfied.)"
        else:
            missing_str = ", ".join([m["code"] for m in missing]) if missing else "unknown prerequisites"
            ans = f"Not yet — to take {plan.target_course}, you’re missing: {missing_str}."
        return plan, [], "", {}, ans, {"verdict": "pass", "reason": "Eligibility computed from graph.", "followup_cypher_hint": ""}

    hint = ""
    last = {"plan": plan.model_dump(), "steps": []}
    rows = []
    ans = ""
    cypher = ""
    params = {}

    for step in range(2):
        cy = build_cypher(llm, plan, question, hint=hint)
        cypher, params = cy.cypher, cy.params
        rows = neo.run_read(cypher, params)

        if plan.intent == "prereq_path":
            path_nodes = extract_shortest_path(rows)
            if path_nodes:
                ans = f"Shortest prerequisite path:\n{format_path_nodes(path_nodes)}"
            else:
                ans = answer_fn(llm, plan, question, rows)
        else:
            ans = answer_fn(llm, plan, question, rows)

        ver = verify_fn(llm, question, rows, ans)
        last["steps"].append({"cypher": cypher, "params": params, "rows": rows, "answer": ans, "verifier": ver.model_dump()})

        if ver.verdict == "pass":
            break
        if ver.verdict == "needs_more" and step == 0:
            hint = ver.followup_cypher_hint or "Retrieve more relevant nodes/relationships."
            continue
        break

    return plan, rows, cypher, params, ans, last["steps"][-1]["verifier"] if last["steps"] else {}

def main():
    st.set_page_config(page_title="Agentic Neo4j Course Advisor", layout="wide")
    st.title("Agentic Neo4j Course & Program Advisor")

    llm, neo = get_clients()

    if "history" not in st.session_state:
        st.session_state.history = []

    col1, col2 = st.columns([2, 1])

    with col1:
        question = st.text_input("Ask a question", placeholder="e.g., What do I need before I can take DMS440?")
        ask = st.button("Ask")

        if ask and question.strip():
            plan, rows, cypher, params, ans, verifier = run_pipeline(llm, neo, question.strip())
            st.session_state.history.append({"q": question, "a": ans, "plan": plan.model_dump(), "cypher": cypher, "params": params, "rows": rows, "verifier": verifier})

    with col1:
        st.subheader("Chat")
        for item in reversed(st.session_state.history[-10:]):
            st.markdown(f"**Q:** {item['q']}")
            st.markdown(f"**A:** {item['a']}")
            st.divider()

    with col2:
        st.subheader("Debug")
        if st.session_state.history:
            last = st.session_state.history[-1]
            with st.expander("Plan", expanded=True):
                st.json(last["plan"])
            with st.expander("Cypher", expanded=True):
                st.code(last["cypher"] or "(eligibility shortcut / no cypher)", language="cypher")
                st.json(last["params"])
            with st.expander("Rows preview", expanded=False):
                if last["rows"]:
                    st.dataframe(pd.DataFrame(last["rows"]).head(25))
                else:
                    st.write("No rows.")
            with st.expander("Verifier", expanded=True):
                st.json(last["verifier"])
        else:
            st.info("Ask a question to see planner, cypher, rows, and verifier output.")

if __name__ == "__main__":
    main()
