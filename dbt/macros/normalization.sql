{% macro normalize_text(expression) -%}
    nullif(trim(cast({{ expression }} as {{ dbt.type_string() }})), '')
{%- endmacro %}

{% macro normalize_code(expression) -%}
    lower(replace(replace({{ normalize_text(expression) }}, '-', '_'), ' ', '_'))
{%- endmacro %}

{% macro normalized_boolean(expression) -%}
    case
        when lower(trim(cast({{ expression }} as {{ dbt.type_string() }})))
            in ('true', 't', '1', 'yes', 'y') then true
        when lower(trim(cast({{ expression }} as {{ dbt.type_string() }})))
            in ('false', 'f', '0', 'no', 'n') then false
        else null
    end
{%- endmacro %}

{% macro safe_date(expression) -%}
    {{ return(adapter.dispatch('safe_date', 'peoplepulse')(expression)) }}
{%- endmacro %}

{% macro postgres__safe_date(expression) -%}
    case
        when trim(cast({{ expression }} as {{ dbt.type_string() }}))
            ~ '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
        then to_date(trim(cast({{ expression }} as {{ dbt.type_string() }})), 'YYYY-MM-DD')
        else null
    end
{%- endmacro %}

{% macro snowflake__safe_date(expression) -%}
    try_to_date({{ expression }})
{%- endmacro %}

{% macro default__safe_date(expression) -%}
    cast({{ expression }} as date)
{%- endmacro %}

{% macro safe_timestamp(expression) -%}
    {{ return(adapter.dispatch('safe_timestamp', 'peoplepulse')(expression)) }}
{%- endmacro %}

{% macro postgres__safe_timestamp(expression) -%}
    cast({{ expression }} as timestamp)
{%- endmacro %}

{% macro snowflake__safe_timestamp(expression) -%}
    try_to_timestamp_ntz({{ expression }})
{%- endmacro %}

{% macro default__safe_timestamp(expression) -%}
    cast({{ expression }} as timestamp)
{%- endmacro %}
