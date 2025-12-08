"""Centralized path configuration for the application."""

import os
from pathlib import Path

def get_data_root() -> Path:
    """
    Get the root directory for data files (evidence, knowledge-graph, etc).
    
    Respects the SPECULUM_DATA_DIR environment variable.
    If not set, defaults to the current working directory.
    """
    env_path = os.getenv("SPECULUM_DATA_DIR")
    if env_path:
        return Path(env_path)
    return Path(".")

def get_evidence_root() -> Path:
    """Get the root directory for evidence files."""
    return get_data_root() / "evidence"

def get_knowledge_graph_root() -> Path:
    """Get the root directory for knowledge graph files."""
    return get_data_root() / "knowledge-graph"

def get_reports_root() -> Path:
    """Get the root directory for report files."""
    return get_data_root() / "reports"

def get_config_file() -> Path:
    """Get the path to the project configuration file."""
    return Path("config/manifest.json")

