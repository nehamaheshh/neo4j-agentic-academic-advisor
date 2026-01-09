
# 🎓 Agentic Graph Advisor  
### A Graph-First, Multi-Agent Academic Question Answering System

**Agentic Graph Advisor** is a **graph-based, multi-agent question answering system** built using **Neo4j** and **local LLMs (Ollama)** to answer complex academic advising questions about **courses, prerequisites, and degree programs**.

Unlike traditional vector-based RAG systems, this project treats the **knowledge graph as the source of truth** and uses LLMs only for **planning, orchestration, and explanation**, not fact generation.

---

## 🚀 What This Project Solves

Academic advising questions are **structural**, not semantic.

Questions like:
- *What do I need before I can take Course X?*
- *Can I take Course X if I’ve completed Courses Y and Z?*
- *What courses does Course X unlock?*
- *What are the core requirements for a degree program?*

cannot be answered reliably using embeddings or similarity search alone.

This project solves that by:
- explicitly modeling relationships as a **knowledge graph**
- performing **multi-hop graph traversal**
- using **deterministic logic** where correctness matters
- orchestrating reasoning through **LLM-based agents**

---

## 🧠 Core Design Principles

- **Graph > Vector Search** for structural reasoning  
- **LLMs are not the source of truth**  
- **Deterministic logic for eligibility checks**  
- **Agentic orchestration with guardrails**  
- **Explainable and debuggable outputs**

---

## 🏗️ System Architecture

```
User Question
     ↓
Planner Agent
(intent classification + entity extraction)
     ↓
Cypher Agent
(read-only Neo4j queries)
     ↓
Neo4j Knowledge Graph
(courses, prerequisites, programs)
     ↓
Answer Agent
(graph-grounded explanation)
     ↓
Verifier Agent
(completeness & hallucination check)
```

A **Streamlit UI** exposes each step of this pipeline for transparency.

---

## 🧩 Knowledge Graph Schema

### Nodes

**Course**
```
Course {
  course_code,
  title,
  credits,
  level,
  description,
  department
}
```

**Program**
```
Program {
  program_id,
  program_name,
  degree_type,
  department
}
```

### Relationships

```
(Course)-[:PREREQUISITE]->(Course)
(Program)-[:REQUIRES {requirement_type}]->(Course)
```

---

## 🤖 Agent Responsibilities

### 1️⃣ Planner Agent
- Classifies user intent (e.g. `all_prereqs`, `eligibility_check`)
- Extracts course codes and program IDs
- Uses **LLM reasoning + rule-based overrides** for reliability

### 2️⃣ Cypher Agent
- Generates **read-only Cypher queries**
- Uses **deterministic templates** for known intents
- Falls back to LLM generation only when necessary

### 3️⃣ Answer Agent
- Converts graph results into **natural language answers**
- Uses deterministic formatting for structured outputs
- Never outputs Cypher, code, or hallucinated facts

### 4️⃣ Verifier Agent
- Ensures answers are supported by graph results
- Detects incomplete responses
- Triggers a follow-up query when needed
- Hardened against malformed LLM output

---

## 🔁 Agentic Reasoning Loop

The system supports a **multi-step agent loop**:

1. Initial query execution  
2. Verifier evaluates completeness  
3. Optional follow-up query with verifier guidance  

---

## 🧪 Supported Question Types

- Course descriptions  
- Direct prerequisites (1-hop)  
- **All prerequisites (transitive closure)**  
- Shortest prerequisite path  
- Program core vs elective requirements  
- Eligibility checks (set-difference logic)  
- Forward dependencies (“what does this course unlock?”)

---

## 📊 Example

**Question**
```
What do I need before I can take DMS440?
```

**Answer**
```
All prerequisites (transitive closure):

- CSE115: Intro to Programming
- CSE116: Object-Oriented Programming
- CSE191: Intro to Data Structures
- CSE250: Data Structures and Algorithms
- CSE305: Database Systems
- CSE404: Machine Learning Foundations
- CSE440: Graph Databases and Neo4j
- DMS201: Intro to Data Science
- DMS301: Data Mining
- DMS401: Applied Machine Learning
- DMS430: Agentic AI Systems
- MTH101: Calculus I
- MTH102: Calculus II
- MTH201: Linear Algebra
- MTH241: Discrete Mathematics
- MTH301: Probability
- MTH302: Statistics
```

---

## 🖥️ Streamlit Interface

The Streamlit UI displays:
- User question  
- Planner output (intent + entities)  
- Generated Cypher query  
- Neo4j result preview  
- Final answer  
- Verifier verdict  

---

## 🛠️ Tech Stack

- **Neo4j** – graph database  
- **Python** – core application logic  
- **Ollama** – local LLM inference  
- **Pydantic** – schema validation  
- **Streamlit** – interactive UI  
- **Docker** – Neo4j deployment  

---

## 📁 Repository Structure

```
agentic-graph-advisor/
├── data/
├── src/
│   ├── agents/
│   ├── db/
│   ├── llm/
│   ├── rag/
│   ├── main.py
│   └── ui_streamlit.py
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🎯 What This Project Demonstrates

- Knowledge graph modeling  
- Agentic AI system design  
- Safe LLM orchestration  
- Multi-hop reasoning  
- Production-style defensive engineering  
- Knowing when **not** to use vector RAG  

---
