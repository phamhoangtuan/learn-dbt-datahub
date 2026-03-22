{% macro is_suspicious_transaction(amount, status) %}
    ({{ amount }} > 10000 AND {{ status }} = 'COMPLETED')
{% endmacro %}
