{% macro datediff_days(start_expression, end_expression) -%}
    {{ return(adapter.dispatch('datediff_days', 'peoplepulse')(start_expression, end_expression)) }}
{%- endmacro %}

{% macro postgres__datediff_days(start_expression, end_expression) -%}
    floor(extract(epoch from (
        cast({{ end_expression }} as timestamp) - cast({{ start_expression }} as timestamp)
    )) / 86400.0)
{%- endmacro %}

{% macro snowflake__datediff_days(start_expression, end_expression) -%}
    datediff(day, {{ start_expression }}, {{ end_expression }})
{%- endmacro %}

{% macro default__datediff_days(start_expression, end_expression) -%}
    datediff(day, {{ start_expression }}, {{ end_expression }})
{%- endmacro %}

{% macro datediff_hours(start_expression, end_expression) -%}
    {{ return(adapter.dispatch('datediff_hours', 'peoplepulse')(start_expression, end_expression)) }}
{%- endmacro %}

{% macro postgres__datediff_hours(start_expression, end_expression) -%}
    extract(epoch from (
        cast({{ end_expression }} as timestamp) - cast({{ start_expression }} as timestamp)
    )) / 3600.0
{%- endmacro %}

{% macro snowflake__datediff_hours(start_expression, end_expression) -%}
    datediff(second, {{ start_expression }}, {{ end_expression }}) / 3600.0
{%- endmacro %}

{% macro default__datediff_hours(start_expression, end_expression) -%}
    datediff(hour, {{ start_expression }}, {{ end_expression }})
{%- endmacro %}

{% macro add_microsecond(expression, amount=-1) -%}
    {{ return(adapter.dispatch('add_microsecond', 'peoplepulse')(expression, amount)) }}
{%- endmacro %}

{% macro postgres__add_microsecond(expression, amount=-1) -%}
    ({{ expression }} + interval '{{ amount }} microsecond')
{%- endmacro %}

{% macro snowflake__add_microsecond(expression, amount=-1) -%}
    dateadd(microsecond, {{ amount }}, {{ expression }})
{%- endmacro %}

{% macro default__add_microsecond(expression, amount=-1) -%}
    {{ expression }}
{%- endmacro %}

{% macro safe_divide(numerator, denominator) -%}
    ({{ numerator }}) * 1.0 / nullif(({{ denominator }}), 0)
{%- endmacro %}

