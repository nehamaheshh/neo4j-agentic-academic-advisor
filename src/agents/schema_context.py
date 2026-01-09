SCHEMA = """
Graph schema:

Nodes:
- (:Course {course_code, title, department, level, credits, description})
- (:Program {program_id, program_name, degree_type, department, description})

Relationships:
- (:Course)-[:PREREQUISITE]->(:Course)   // pre -> target
- (:Program)-[:REQUIRES {requirement_type}]->(:Course)  // Core/Elective

Only generate READ-ONLY Cypher.
Allowed keywords: MATCH, WHERE, WITH, RETURN, ORDER BY, LIMIT.
Never use CREATE/MERGE/SET/DELETE/CALL/LOAD CSV.

Course codes look like: CSE305, DMS440, MTH201
Program ids: MSDS, BSCS, BASTAT
"""
