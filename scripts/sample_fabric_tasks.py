"""
AADAP — Sample Fabric Tasks
================================
Sample tasks to test end-to-end AADAP functionality with Microsoft Fabric.

These mirror the Databricks ``sample_tasks.py`` but target Fabric Spark
notebooks and Lakehouse SQL endpoints.

Usage — as a library:
    from scripts.sample_fabric_tasks import SAMPLE_FABRIC_PYTHON_TASK
    # pass to ExecutionService or POST /api/tasks

Usage — standalone:
    python scripts/sample_fabric_tasks.py
"""

from __future__ import annotations

# ── Python tasks (Fabric Spark Notebook) ───────────────────────────────

SAMPLE_FABRIC_PYTHON_TASK = {
    "title": "Fabric Test - Lakehouse Read",
    "description": (
        "Read the first 10 rows from a Lakehouse table to verify "
        "Fabric Spark connectivity.\n\n"
        "Python code to execute:\n"
        "  df = spark.sql('SELECT * FROM lakehouse.sample_table LIMIT 10')\n"
        "  df.show()\n"
        "  print(f'Row count: {df.count()}')\n\n"
        "Expected outcome:\n"
        "- Spark session is available on Fabric\n"
        "- Lakehouse table is accessible\n"
        "- First 10 rows are displayed\n\n"
        "This is a safe, read-only test."
    ),
    "environment": "SANDBOX",
    "language": "python",
    "agent_type": "fabric-python",
    "priority": 0,
    "metadata": {"platform": "fabric"},
}

SAMPLE_FABRIC_PYTHON_NOTEBOOKUTILS = {
    "title": "Fabric Test - notebookutils File List",
    "description": (
        "Use notebookutils to list files in the Lakehouse Files section.\n\n"
        "Python code to execute:\n"
        "  files = notebookutils.fs.ls('Files/')\n"
        "  for f in files:\n"
        "      print(f.name, f.size)\n\n"
        "Expected outcome:\n"
        "- notebookutils is available\n"
        "- Files in the Lakehouse are listed\n\n"
        "This tests Fabric-native API availability."
    ),
    "environment": "SANDBOX",
    "language": "python",
    "agent_type": "fabric-python",
    "priority": 0,
    "metadata": {"platform": "fabric"},
}


# ── Scala tasks (Fabric Spark Notebook) ────────────────────────────────

SAMPLE_FABRIC_SCALA_TASK = {
    "title": "Fabric Test - Scala DataFrame",
    "description": (
        "Create a simple Spark DataFrame using Scala on Fabric.\n\n"
        "Scala code to execute:\n"
        "  val df = spark.range(10)\n"
        "  df.show()\n"
        "  println(s\"Count: ${df.count()}\")\n\n"
        "Expected outcome:\n"
        "- Scala/Spark is available on Fabric\n"
        "- DataFrame with 10 rows is created and displayed\n\n"
        "This tests Scala runtime availability."
    ),
    "environment": "SANDBOX",
    "language": "scala",
    "agent_type": "fabric-scala",
    "priority": 0,
    "metadata": {"platform": "fabric"},
}


# ── SQL tasks (Fabric Lakehouse / Warehouse) ──────────────────────────

SAMPLE_FABRIC_SQL_TASK = {
    "title": "Fabric Test - SQL Connectivity",
    "description": (
        "Execute a simple SQL query on the Fabric SQL endpoint.\n\n"
        "SQL to execute:\n"
        "  SELECT CURRENT_TIMESTAMP AS test_time, 1 + 1 AS calculation\n\n"
        "Expected outcome:\n"
        "- SQL endpoint is reachable\n"
        "- Query returns current timestamp and basic arithmetic\n"
        "- Minimal compute cost\n\n"
        "This is a safe, read-only test."
    ),
    "environment": "SANDBOX",
    "language": "sql",
    "agent_type": "fabric-sql",
    "priority": 0,
    "metadata": {"platform": "fabric"},
}

SAMPLE_FABRIC_SQL_DELTA = {
    "title": "Fabric Test - Delta Lake Time Travel",
    "description": (
        "Demonstrate Delta Lake time-travel on a Lakehouse table.\n\n"
        "SQL to execute:\n"
        "  SELECT * FROM lakehouse.sample_table VERSION AS OF 0 LIMIT 5\n\n"
        "Expected outcome:\n"
        "- Delta Lake is available on the SQL endpoint\n"
        "- Version 0 of the table is accessible\n"
        "- First 5 rows of the initial snapshot are returned\n\n"
        "This tests Delta Lake features on Fabric."
    ),
    "environment": "SANDBOX",
    "language": "sql",
    "agent_type": "fabric-sql",
    "priority": 0,
    "metadata": {"platform": "fabric"},
}

SAMPLE_FABRIC_SQL_SHOW_TABLES = {
    "title": "Fabric Test - List Lakehouse Tables",
    "description": (
        "List all tables in the Fabric Lakehouse.\n\n"
        "SQL to execute:\n"
        "  SHOW TABLES\n\n"
        "Expected outcome:\n"
        "- Lakehouse SQL endpoint is reachable\n"
        "- All tables in the default schema are listed\n\n"
        "This is a safe, read-only test."
    ),
    "environment": "SANDBOX",
    "language": "sql",
    "agent_type": "fabric-sql",
    "priority": 0,
    "metadata": {"platform": "fabric"},
}


# ── Catalog (all sample tasks) ─────────────────────────────────────────

ALL_FABRIC_SAMPLE_TASKS = [
    SAMPLE_FABRIC_PYTHON_TASK,
    SAMPLE_FABRIC_PYTHON_NOTEBOOKUTILS,
    SAMPLE_FABRIC_SCALA_TASK,
    SAMPLE_FABRIC_SQL_TASK,
    SAMPLE_FABRIC_SQL_DELTA,
    SAMPLE_FABRIC_SQL_SHOW_TABLES,
]


if __name__ == "__main__":
    print("Sample Test Tasks for AADAP + Microsoft Fabric")
    print("=" * 60)

    print("\n--- Python Tasks (Fabric Spark Notebook) ---")
    for i, task in enumerate(
        [SAMPLE_FABRIC_PYTHON_TASK, SAMPLE_FABRIC_PYTHON_NOTEBOOKUTILS], 1
    ):
        print(f"\n{i}. {task['title']}")
        print(f"   Agent : {task['agent_type']}")
        print(f"   Lang  : {task['language']}")

    print("\n--- Scala Tasks (Fabric Spark Notebook) ---")
    print(f"\n3. {SAMPLE_FABRIC_SCALA_TASK['title']}")
    print(f"   Agent : {SAMPLE_FABRIC_SCALA_TASK['agent_type']}")
    print(f"   Lang  : {SAMPLE_FABRIC_SCALA_TASK['language']}")

    print("\n--- SQL Tasks (Fabric Lakehouse / Warehouse) ---")
    for i, task in enumerate(
        [SAMPLE_FABRIC_SQL_TASK, SAMPLE_FABRIC_SQL_DELTA,
            SAMPLE_FABRIC_SQL_SHOW_TABLES],
        4,
    ):
        print(f"\n{i}. {task['title']}")
        print(f"   Agent : {task['agent_type']}")
        print(f"   Lang  : {task['language']}")

    print("\n" + "=" * 60)
    print("To test via API:")
    print("  POST /api/tasks")
    print("  Content-Type: application/json")
    print("  ", SAMPLE_FABRIC_PYTHON_TASK)
    print("\nAll tasks use metadata={'platform': 'fabric'} for routing.")
