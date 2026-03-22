{#
  Emulator compatibility overrides.

  The Snowflake emulator (DuckDB-backed) does not support several SHOW commands
  that dbt >= 1.10 sends during schema discovery:
    - SHOW TERSE SCHEMAS IN DATABASE ...
    - SHOW TERSE OBJECTS IN SCHEMA ...

  These macros override the snowflake adapter defaults to use simple SELECT
  statements instead of SHOW commands, compatible with the emulator.
#}

{% macro snowflake__list_schemas(database) %}
    {#
      Return the known schema directly as a list of dicts so the adapter's
        [row["name"] for row in results]
      works without any SHOW commands (unsupported by the emulator).
    #}
    {{ return([{"name": "RAW"}]) }}
{% endmacro %}


{% macro snowflake__list_relations_without_caching(schema_relation) %}
    {#
      information_schema.tables fails in the emulator (connector wraps table name
      in backticks which DuckDB rejects). Use duckdb_tables() instead.
    #}
    {#
      The emulator returns rowset=null for zero-row SELECTs, which the proxy
      misidentifies as a DDL response. Avoid empty results by using UNION ALL
      of the known tables in this project. dbt uses CREATE OR REPLACE TABLE
      so pre-seeding the cache with known table names is safe.
    #}
    {% set db = schema_relation.database %}
    {% set sch = schema_relation.schema %}
    {# All source + model tables expected in this project #}
    {% set known = [
        'ACCOUNTS_RAW', 'TRANSACTIONS_RAW',
        'BRONZE_ACCOUNTS_RAW', 'BRONZE_TRANSACTIONS_RAW',
        'SILVER_ACCOUNTS_CLEAN', 'SILVER_TRANSACTIONS_CLEAN',
        'GOLD_DAILY_BALANCE_SNAPSHOT', 'GOLD_TRANSACTION_SUMMARY'
    ] %}
    {% set row_literals = [] %}
    {% for tname in known %}
        {% do row_literals.append(
            "('" ~ db ~ "', '" ~ sch ~ "', '" ~ tname ~ "', 'table', 0)"
        ) %}
    {% endfor %}
    {% set sql %}
        select database_name, schema_name, name, kind, is_dynamic
        from (values {{ row_literals | join(', ') }}) as t(database_name, schema_name, name, kind, is_dynamic)
    {% endset %}
    {{ return(run_query(sql)) }}
{% endmacro %}
