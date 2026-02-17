"""
AADAP — Sample Test Tasks
=========================
Sample tasks to test end-to-end AADAP functionality with Databricks.

This demonstrates low-cost tasks that can be used to verify the integration
without requiring complex data pipelines or job creation.
"""

SAMPLE_SQL_TASK = {
    "title": "Test Query - Current Timestamp",
    "description": """
Execute a simple SQL query to verify Databricks connectivity.
This task runs: SELECT current_timestamp() as test_time, 1+1 as calculation

Expected outcome:
- Query executes successfully on SQL Warehouse
- Returns current timestamp and result of 1+1
- Low cost: minimal warehouse compute time (< 5 seconds)

This is a safe, read-only test that:
- Does not modify any data
- Does not create any objects
- Uses minimal compute resources
- Completes in seconds
""",
    "environment": "SANDBOX",
    "language": "sql",
    "priority": 0,
}

SAMPLE_SQL_LIST_TABLES = {
    "title": "Test - List Available Tables",
    "description": """
Query the catalog to list available tables in the current schema.

SQL to execute:
  SHOW TABLES

This will display all tables accessible in the configured catalog/schema.
Safe, read-only operation that helps verify permissions and connectivity.
""",
    "environment": "SANDBOX",
    "language": "sql",
    "priority": 0,
}

SAMPLE_PYTHON_TASK = {
    "title": "Test Python - Basic Calculation",
    "description": """
Execute a simple Python script to verify cluster connectivity.

Python code to execute:
  print("Hello from Databricks!")
  result = 2 + 2
  print(f"2 + 2 = {result}")

Expected outcome:
- Python code executes on Compute Cluster
- Output shows "Hello from Databricks!" and "2 + 2 = 4"
- Low cost: minimal cluster compute time

This is a safe test that:
- Does not access any data
- Does not create any objects
- Uses minimal compute resources
""",
    "environment": "SANDBOX",
    "language": "python",
    "priority": 0,
}

SAMPLE_PYTHON_SPARK_TASK = {
    "title": "Test Python - Spark DataFrame",
    "description": """
Execute Python code that uses Spark to create a simple DataFrame.

Python code to execute:
  df = spark.range(10)
  df.show()
  print(f"Count: {df.count()}")

Expected outcome:
- Spark session is available
- DataFrame with 10 rows is created and displayed
- Count is printed

This tests:
- Spark availability
- Basic DataFrame operations
- Cluster connectivity
""",
    "environment": "SANDBOX",
    "language": "python",
    "priority": 0,
}

SAMPLE_PYTHON_QUERY_TASK = {
    "title": "Test Python - Run SQL via Spark",
    "description": """
Execute Python code that runs SQL via Spark SQL.

Python code to execute:
  result = spark.sql("SELECT current_timestamp(), 1+1 as calc")
  result.show()

Expected outcome:
- Spark SQL is available
- SQL query runs via Python
- Results are displayed

This tests the ability to run SQL from Python code.
""",
    "environment": "SANDBOX",
    "language": "python",
    "priority": 0,
}


def get_sample_sql_for_description(description: str) -> str:
    """
    Extract or generate SQL from a task description.

    This is a simple helper for demonstration. In production,
    the LLM would generate the SQL based on the description.
    """
    description_lower = description.lower()

    if "current_timestamp" in description_lower or "test query" in description_lower:
        return "SELECT current_timestamp() as test_time, 1+1 as calculation"

    if "show tables" in description_lower or "list available tables" in description_lower:
        return "SHOW TABLES"

    if "describe schema" in description_lower:
        return "DESCRIBE SCHEMA"

    if "describe table" in description_lower:
        return "DESCRIBE SCHEMA"

    return "SELECT 1 as test"


def get_sample_python_for_description(description: str) -> str:
    """
    Extract or generate Python code from a task description.
    """
    description_lower = description.lower()

    if "spark dataframe" in description_lower:
        return """df = spark.range(10)
df.show()
print(f"Count: {df.count()}")"""

    if "spark sql" in description_lower or "run sql via spark" in description_lower:
        return """result = spark.sql("SELECT current_timestamp(), 1+1 as calc")
result.show()"""

    if "basic calculation" in description_lower or "hello from databricks" in description_lower:
        return """print("Hello from Databricks!")
result = 2 + 2
print(f"2 + 2 = {result}")"""

    return 'print("Python execution test")'


if __name__ == "__main__":
    print("Sample Test Tasks for AADAP + Databricks")
    print("=" * 60)

    print("\n--- SQL Tasks (SQL Warehouse) ---")
    print("\n1. Quick Connectivity Test:")
    print(f"   Title: {SAMPLE_SQL_TASK['title']}")
    print(f"   SQL: {get_sample_sql_for_description(SAMPLE_SQL_TASK['description'])}")

    print("\n2. List Tables Test:")
    print(f"   Title: {SAMPLE_SQL_LIST_TABLES['title']}")
    print(f"   SQL: {get_sample_sql_for_description(SAMPLE_SQL_LIST_TABLES['description'])}")

    print("\n--- Python Tasks (Compute Cluster) ---")
    print("\n3. Basic Python Test:")
    print(f"   Title: {SAMPLE_PYTHON_TASK['title']}")
    print(f"   Python:\n{get_sample_python_for_description(SAMPLE_PYTHON_TASK['description'])}")

    print("\n4. Spark DataFrame Test:")
    print(f"   Title: {SAMPLE_PYTHON_SPARK_TASK['title']}")
    print(f"   Python:\n{get_sample_python_for_description(SAMPLE_PYTHON_SPARK_TASK['description'])}")

    print("\n5. Spark SQL Test:")
    print(f"   Title: {SAMPLE_PYTHON_QUERY_TASK['title']}")
    print(f"   Python:\n{get_sample_python_for_description(SAMPLE_PYTHON_QUERY_TASK['description'])}")

    print("\n" + "=" * 60)
    print("To test via API:")
    print("  POST /api/tasks")
    print("  Content-Type: application/json")
    print("  ", SAMPLE_SQL_TASK)
    print("\nOr run the connection test:")
    print("  python scripts/test_databricks_connection.py")
