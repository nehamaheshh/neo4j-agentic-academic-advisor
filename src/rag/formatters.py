from typing import Any, Dict, List

def format_course_node(n: Dict[str, Any]) -> str:
    # nodes(p) returns dict-like nodes with properties
    code = n.get("course_code", "")
    title = n.get("title", "")
    return f"{code} ({title})" if title else code

def format_path_nodes(path_nodes: List[Dict[str, Any]]) -> str:
    # Example output: A → B → C
    return " \u2192 ".join([n.get("course_code", "?") for n in path_nodes])

def extract_shortest_path(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Expect rows like: {"path_nodes": [...], "hops": 3}
    if not rows:
        return []
    if "path_nodes" in rows[0]:
        return rows[0]["path_nodes"]
    return []
