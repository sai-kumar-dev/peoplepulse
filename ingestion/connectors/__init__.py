"""Built-in source connectors."""

from ingestion.connectors.base import SourceConnector
from ingestion.connectors.csv_connector import CSVConnector
from ingestion.connectors.json_connector import JSONConnector
from ingestion.connectors.postgres import PostgreSQLConnector
from ingestion.connectors.rest import RESTConnector

__all__ = [
    "CSVConnector",
    "JSONConnector",
    "PostgreSQLConnector",
    "RESTConnector",
    "SourceConnector",
]
