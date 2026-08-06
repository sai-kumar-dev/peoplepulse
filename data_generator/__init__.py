"""Deterministic synthetic workforce data for PeoplePulse."""

from data_generator.generators import generate_dataset
from data_generator.models import GeneratedDataset, GenerationConfig

__all__ = ["GeneratedDataset", "GenerationConfig", "generate_dataset"]
