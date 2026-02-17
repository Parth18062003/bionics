"""
AADAP — Databricks Connection Test
====================================
Quick test script to verify Databricks connectivity for both SQL and Python.

Run this script to test your Databricks configuration:
    python scripts/test_databricks_connection.py

Prerequisites:
    1. Databricks CLI authenticated: `databricks auth login`
    2. Set environment variables in .env:
        - AADAP_DATABRICKS_HOST (required)
        - AADAP_DATABRICKS_WAREHOUSE_ID (for SQL)
        - AADAP_DATABRICKS_CLUSTER_ID (for Python)
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_sql(client):
    """Test SQL execution via SQL Warehouse."""
    print("\n" + "=" * 60)
    print("Testing SQL Execution (SQL Warehouse)")
    print("=" * 60)

    if not client._warehouse_id:
        print("\n[SKIP] No warehouse_id configured (set AADAP_DATABRICKS_WAREHOUSE_ID)")
        return None

    test_sql = "SELECT current_timestamp() as test_time, 1+1 as calculation"

    print(f"\n[INFO] Executing test query...")
    print(f"       SQL: {test_sql}")

    try:
        submission = await client.submit_job(
            task_id=uuid.uuid4(),
            code=test_sql,
            environment="SANDBOX",
            language="sql",
        )
        print(f"\n[OK] Statement submitted")
        print(f"     Statement ID: {submission.job_id}")

        status = await client.get_job_status(submission.job_id)
        print(f"\n[OK] Statement status: {status.value}")

        if status.value == "SUCCESS":
            result = await client.get_job_output(submission.job_id)
            print(f"\n[OK] Statement output:")
            print(f"     Status: {result.status.value}")
            print(f"     Duration: {result.duration_ms}ms")
            print(f"     Output:\n{result.output}")
            return True
        else:
            result = await client.get_job_output(submission.job_id)
            print(f"\n[ERROR] Statement failed")
            print(f"     Error: {result.error}")
            return False

    except Exception as e:
        print(f"\n[ERROR] SQL execution failed: {e}")
        return False


async def test_python(client):
    """Test Python execution via Compute Cluster."""
    print("\n" + "=" * 60)
    print("Testing Python Execution (Compute Cluster)")
    print("=" * 60)

    from aadap.integrations.databricks_client import JobStatus

    if not client._cluster_id:
        print("\n[SKIP] No cluster_id configured (set AADAP_DATABRICKS_CLUSTER_ID)")
        return None

    test_code = """
print("Hello from Databricks!")
result = 2 + 2
print(f"2 + 2 = {result}")
spark.sql("SELECT 1 as test").show()
""".strip()

    print(f"\n[INFO] Executing Python code...")
    print(f"       Code:\n{test_code}")

    try:
        submission = await client.submit_job(
            task_id=uuid.uuid4(),
            code=test_code,
            environment="SANDBOX",
            language="python",
        )
        print(f"\n[OK] Command submitted")
        print(f"     Command ID: {submission.job_id}")

        import asyncio
        status = JobStatus.PENDING
        for _ in range(30):
            status = await client.get_job_status(submission.job_id)
            if status.value in ("SUCCESS", "FAILED", "CANCELLED"):
                break
            await asyncio.sleep(2)

        print(f"\n[OK] Command status: {status.value}")

        result = await client.get_job_output(submission.job_id)
        if status.value == "SUCCESS":
            print(f"\n[OK] Command output:")
            print(f"     Duration: {result.duration_ms}ms")
            print(f"     Output:\n{result.output}")
            return True
        else:
            print(f"\n[ERROR] Command failed")
            print(f"     Error: {result.error}")
            return False

    except Exception as e:
        print(f"\n[ERROR] Python execution failed: {e}")
        return False


async def test_connection():
    from aadap.integrations.databricks_client import DatabricksClient

    print("=" * 60)
    print("AADAP Databricks Connection Test")
    print("=" * 60)

    try:
        client = DatabricksClient.from_settings()
        print(f"\n[OK] Client initialized")
        print(f"     Host: {client._host}")
        print(f"     Warehouse ID: {client._warehouse_id or '(not set)'}")
        print(f"     Cluster ID: {client._cluster_id or '(not set)'}")
        print(f"     Catalog: {client._catalog or '(default)'}")
        print(f"     Schema: {client._schema or '(default)'}")
    except ValueError as e:
        print(f"\n[ERROR] Configuration missing: {e}")
        print("\nPlease set the following environment variables:")
        print("  - AADAP_DATABRICKS_HOST (required)")
        print("  - AADAP_DATABRICKS_WAREHOUSE_ID (for SQL)")
        print("  - AADAP_DATABRICKS_CLUSTER_ID (for Python)")
        return False

    sql_ok = await test_sql(client)
    python_ok = await test_python(client)

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"  SQL:    {'PASS' if sql_ok else 'FAIL' if sql_ok is False else 'SKIP'}")
    print(f"  Python: {'PASS' if python_ok else 'FAIL' if python_ok is False else 'SKIP'}")

    if sql_ok or python_ok:
        print("\n[SUCCESS] At least one execution method works!")
        return True
    elif sql_ok is None and python_ok is None:
        print("\n[WARNING] No execution methods configured")
        return False
    else:
        print("\n[FAILED] All configured execution methods failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
