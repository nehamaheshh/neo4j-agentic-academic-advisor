import csv
import os
from dotenv import load_dotenv
from src.db.neo4j_client import Neo4jClient

load_dotenv()

def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def main():
    neo = Neo4jClient(
        os.environ["NEO4J_URI"],
        os.environ["NEO4J_USER"],
        os.environ["NEO4J_PASSWORD"],
    )

    # Constraints
    neo.run_write("CREATE CONSTRAINT course_code IF NOT EXISTS FOR (c:Course) REQUIRE c.course_code IS UNIQUE;")
    neo.run_write("CREATE CONSTRAINT program_id IF NOT EXISTS FOR (p:Program) REQUIRE p.program_id IS UNIQUE;")

    courses = read_csv("data/courses.csv")
    programs = read_csv("data/programs.csv")
    prereqs = read_csv("data/course_prereqs.csv")
    requires = read_csv("data/program_requires.csv")

    # Upsert courses
    neo.run_write("""
    UNWIND $rows AS row
    MERGE (c:Course {course_code: row.course_code})
    SET c.title = row.title,
        c.department = row.department,
        c.level = row.level,
        c.credits = toInteger(row.credits),
        c.description = row.description;
    """, {"rows": courses})

    # Upsert programs
    neo.run_write("""
    UNWIND $rows AS row
    MERGE (p:Program {program_id: row.program_id})
    SET p.program_name = row.program_name,
        p.degree_type = row.degree_type,
        p.department = row.department,
        p.description = row.description;
    """, {"rows": programs})

    # Prereq edges
    neo.run_write("""
    UNWIND $rows AS row
    MATCH (c:Course {course_code: row.course_code})
    MATCH (pre:Course {course_code: row.prereq_code})
    MERGE (pre)-[:PREREQUISITE]->(c);
    """, {"rows": prereqs})

    # Program requires edges
    neo.run_write("""
    UNWIND $rows AS row
    MATCH (p:Program {program_id: row.program_id})
    MATCH (c:Course {course_code: row.course_code})
    MERGE (p)-[r:REQUIRES]->(c)
    SET r.requirement_type = row.requirement_type;
    """, {"rows": requires})

    # Verify counts
    counts = neo.run_read("""
    MATCH (c:Course) WITH count(c) AS courses
    MATCH (p:Program) WITH courses, count(p) AS programs
    MATCH ()-[r:PREREQUISITE]->() WITH courses, programs, count(r) AS prereqs
    MATCH ()-[r:REQUIRES]->() RETURN courses, programs, prereqs, count(r) AS requires;
    """)
    print(counts[0])

    neo.close()

if __name__ == "__main__":
    main()
