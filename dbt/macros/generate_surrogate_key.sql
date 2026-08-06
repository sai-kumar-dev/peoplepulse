{% macro generate_surrogate_key(fields) -%}
    md5(
        {%- for field in fields -%}
        coalesce(cast({{ field }} as {{ dbt.type_string() }}), '__dbt_null__')
        {%- if not loop.last %} || '|' || {% endif -%}
        {%- endfor -%}
    )
{%- endmacro %}

{% macro unknown_surrogate_key() -%}
    {{ generate_surrogate_key(["'__UNKNOWN__'"]) }}
{%- endmacro %}

