{% macro snapshot_date() -%}
    {%- set configured_snapshot_date = var('snapshot_date', none) -%}
    {%- if configured_snapshot_date is none or configured_snapshot_date == '' -%}
        cast('{{ run_started_at.strftime("%Y-%m-%d") }}' as date)
    {%- else -%}
        cast('{{ configured_snapshot_date }}' as date)
    {%- endif -%}
{%- endmacro %}

