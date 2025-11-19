"""Utilities for Copilot agent workflows over the knowledge base."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Sequence

import yaml




if TYPE_CHECKING:
    from src.integrations.github.assign_copilot import IssueDetails






