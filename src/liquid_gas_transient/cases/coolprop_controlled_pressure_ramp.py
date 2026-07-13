"""CoolProp single-phase controlled-pressure-ramp verification runner.

This module verifies the software/numerical path for a prescribed right-boundary
pressure ramp. It is not physical Validation, design-use acceptance, or an
equipment-performance model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..boundary import LinearPressureRamp, PressureTankBoundary, TransmissiveBoundary
from ..