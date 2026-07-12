"""Stage 5 PR-C mesh/CFL observations for ideal boundary reflections.

Software/numerical verification only; not physical Validation or design-use
acceptance. Rigid-wall and fixed-pressure boundaries remain idealizations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv, json, math, time
from pathlib import Path
from typing import Any

import numpy as np

from .cool