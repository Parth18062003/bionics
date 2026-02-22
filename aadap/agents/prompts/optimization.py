"""
AADAP — Optimization Agent Prompt Templates
===============================================
Prompts for PySpark performance optimization.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md §Agents in Scope.
"""

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput


OPTIMIZATION_OUTPUT_SCHEMA = StructuredOutput(
    fields={
        "optimized_code": "str — optimized Python/PySpark code",
        "changes": "list[dict] — list of optimizations applied, each with description and rationale",
        "expected_improvement": "str — description of expected performance improvement",
    },
    required={"optimized_code", "changes", "expected_improvement"},
)


OPTIMIZATION_EXAMPLES = """
## Example 1: Broadcast Join Optimization

Original Code:
```python
orders = spark.read.table('main.sales.orders')
customers = spark.read.table('main.catalog.customers')
result = orders.join(customers, orders.customer_id == customers.id)
```

Optimized Output:
```json
{
  "optimized_code": "from pyspark.sql.functions import broadcast\\n\\norders = spark.read.table('main.sales.orders')\\ncustomers = spark.read.table('main.catalog.customers')\\nresult = orders.join(broadcast(customers), orders.customer_id == customers.id)",
  "changes": [
    {
      "type": "broadcast_join",
      "description": "Added broadcast hint for customers table",
      "rationale": "Customers dimension table is small (<10MB), broadcast avoids shuffle"
    }
  ],
  "expected_improvement": "50-70% reduction in query time by avoiding shuffle for small table join"
}
```

## Example 2: Partitioning and Caching

Original Code:
```python
df = spark.read.table('main.events.logs')
df1 = df.filter(col('level') == 'ERROR')
df2 = df.filter(col('level') == 'WARN')
df1.write.saveAsTable('errors')
df2.write.saveAsTable('warnings')
```

Optimized Output:
```json
{
  "optimized_code": "df = spark.read.table('main.events.logs').cache()\\ndf1 = df.filter(col('level') == 'ERROR')\\ndf2 = df.filter(col('level') == 'WARN')\\ndf1.write.saveAsTable('errors')\\ndf2.write.saveAsTable('warnings')\\ndf.unpersist()",
  "changes": [
    {
      "type": "caching",
      "description": "Added .cache() to source DataFrame",
      "rationale": "DataFrame is used twice; caching avoids reading source table twice"
    },
    {
      "type": "cleanup",
      "description": "Added unpersist() after use",
      "rationale": "Frees memory after processing to prevent memory pressure"
    }
  ],
  "expected_improvement": "40-50% reduction in total runtime by avoiding repeated table scans"
}
```

## Example 3: Column Pruning and Predicate Pushdown

Original Code:
```python
df = spark.read.table('main.sales.transactions')
result = df.filter(year('date') == 2024).select('id', 'amount', 'date')
```

Optimized Output:
```json
{
  "optimized_code": "df = spark.read.table('main.sales.transactions').select('id', 'amount', 'date')\\nresult = df.filter(col('date').between('2024-01-01', '2024-12-31'))",
  "changes": [
    {
      "type": "column_pruning",
      "description": "Pushed column selection to read",
      "rationale": "Reading only needed columns reduces I/O and memory usage"
    },
    {
      "type": "predicate_pushdown",
      "description": "Changed year() to date range filter",
      "rationale": "Range filter can be pushed down to Delta/Databricks; year() prevents pushdown"
    }
  ],
  "expected_improvement": "30-40% reduction in scan time by pushing predicates to storage layer"
}
```

## Example 4: Delta Lake Optimization

Original Code:
```python
df.write.format('delta').mode('overwrite').save('/path/to/table')
```

Optimized Output:
```json
{
  "optimized_code": "(df.write\\n    .format('delta')\\n    .mode('overwrite')\\n    .option('optimizeWrite', 'true')\\n    .option('autoCompact', 'true')\\n    .save('/path/to/table'))",
  "changes": [
    {
      "type": "optimize_write",
      "description": "Enabled Delta optimizeWrite",
      "rationale": "Automatically optimizes file sizes during write"
    },
    {
      "type": "auto_compact",
      "description": "Enabled Delta autoCompact",
      "rationale": "Automatically compacts small files after write"
    }
  ],
  "expected_improvement": "Improved read performance by 20-30% through optimized file sizes"
}
```
"""


DATABRICKS_PATTERNS = """
Platform-specific patterns for Azure Databricks:
1. Use Delta Lake OPTIMIZE + ZORDER for read-heavy tables
2. Enable Photon acceleration where available (photon_enabled=true)
3. Leverage Adaptive Query Execution (AQE) — avoid manual repartition when AQE is on
4. Prefer Delta MERGE over delete-insert for upserts
5. Use predictive I/O and liquid clustering for large tables
6. Broadcast small dimension tables (<= 10 MB) explicitly
7. Use partition pruning with partition filters
8. Enable auto-optimizer for Delta tables
"""


FABRIC_PATTERNS = """
Platform-specific patterns for Microsoft Fabric:
1. Apply V-Order on write for faster downstream reads
2. Use Z-Order on high-cardinality filter columns
3. Leverage OneLake caching for repeatedly accessed tables
4. Use optimized Delta writes (optimizeWrite, autoCompaction)
5. Prefer Fabric-native connectors over generic Spark connectors
6. Avoid excessive small files — enable autoCompaction
7. Use lakehouse shortcuts for cross-workspace access
"""


OPTIMIZATION_OPTIMIZE_PROMPT = PromptTemplate(
    name="optimization_pyspark",
    system_role=(
        "You are a PySpark optimization specialist for Databricks and Microsoft Fabric. "
        "You analyze existing PySpark code and apply performance optimizations including "
        "partitioning strategies, caching, broadcast joins, predicate pushdown, and shuffle reduction. "
        "Your optimizations must preserve the original code's correctness and semantics.\n\n"
        "Here are examples of optimization outputs:\n"
        + OPTIMIZATION_EXAMPLES
    ),
    constraints=[
        "Optimized code MUST produce the same results as the original.",
        "You MUST NOT change the code's functional semantics.",
        "You MUST list every optimization applied with its rationale.",
        "You MUST describe expected performance improvement.",
        "You MUST consider: partitioning, caching, broadcast joins, predicate pushdown, column pruning, and shuffle reduction.",
        "You MUST NOT introduce new dependencies without justification.",
        "Optimized code MUST be syntactically valid Python.",
        "You MUST apply platform-specific optimizations for the target platform.",
    ],
    output_schema=OPTIMIZATION_OUTPUT_SCHEMA,
    task_instruction=(
        "Optimize the following PySpark code for performance:\n\n"
        "```python\n{code}\n```\n\n"
        "Context: {context}\n"
        "Target Environment: {environment}\n\n"
        "Apply all applicable optimizations and explain each change.\n\n"
        + DATABRICKS_PATTERNS
        + "\n"
        + FABRIC_PATTERNS
    ),
)


OPTIMIZATION_PROMPTS = {
    "optimize": OPTIMIZATION_OPTIMIZE_PROMPT,
}
