import os
from dotenv import load_dotenv
from rich import print

from src.db.neo4j_client import Neo4jClient
from src.llm.ollama_client import OllamaClient
from src.agents.planner import make_plan
from src.agents.cypher_agent import build_cypher
from src.agents.answer_agent import answer as answer_fn
from src.agents.verifier import verify as verify_fn

from src.rag.eligibility import check_eligibility
from src.rag.formatters import extract_shortest_path, format_path_nodes

load_dotenv()

def main():
    llm = OllamaClient(os.environ["OLLAMA_BASE_URL"], os.environ["OLLAMA_MODEL"])
    neo = Neo4jClient(os.environ["NEO4J_URI"], os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])

    print("[bold cyan]Graph QA (type 'exit' to quit)[/bold cyan]")
    while True:
        q = input("\nQuestion> ").strip()
        if q.lower() in ("exit", "quit"):
            break

        plan = make_plan(llm, q)
        print("\n[bold]Plan[/bold]")
        print(plan.model_dump())

        # ---- Eligibility shortcut (deterministic + impressive) ----
        if plan.intent == "eligibility_check" and plan.target_course:
            eligible, missing = check_eligibility(neo, plan.target_course, plan.completed_courses)
            if eligible:
                ans = f"Yes — you appear eligible to take {plan.target_course}. (All prerequisites are satisfied based on the graph.)"
            else:
                missing_str = ", ".join([m["code"] for m in missing]) if missing else "unknown prerequisites"
                ans = f"Not yet — to take {plan.target_course}, you’re missing: {missing_str}."
            print("\n[bold green]Answer[/bold green]")
            print(ans)
            continue

        # ---- Agentic loop with verifier follow-up ----
        hint = ""
        rows = []
        ans = ""
        for step in range(2):
            cy = build_cypher(llm, plan, q, hint=hint)
            print(f"\n[bold]Cypher (step {step+1})[/bold]")
            print(cy.cypher)
            print("[bold]Params[/bold]")
            print(cy.params)

            rows = neo.run_read(cy.cypher, cy.params)
            print(f"\n[bold]Rows[/bold] ({len(rows)})")
            print(rows[:5] if len(rows) > 5 else rows)

            # Pretty path output support (if cypher returned path_nodes)
            if plan.intent == "prereq_path":
                path_nodes = extract_shortest_path(rows)
                if path_nodes:
                    pretty = format_path_nodes(path_nodes)
                    ans = f"Shortest prerequisite path to {plan.course_codes[0] if plan.course_codes else ''}:\n{pretty}"
                else:
                    ans = answer_fn(llm, plan, q, rows)
            else:
                ans = answer_fn(llm, plan, q, rows)

            print("\n[bold green]Answer[/bold green]")
            print(ans)

            ver = verify_fn(llm, q, rows, ans)
            print("\n[bold magenta]Verifier[/bold magenta]")
            print(ver.model_dump())

            if ver.verdict == "pass":
                break
            if ver.verdict == "needs_more" and step == 0:
                hint = ver.followup_cypher_hint or "Retrieve more relevant course/program nodes and relationships."
                continue
            break

    neo.close()

if __name__ == "__main__":
    main()
