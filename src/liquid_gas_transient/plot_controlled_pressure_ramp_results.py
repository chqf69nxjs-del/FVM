"""Generate headless-safe plots from Stage 6 controlled-pressure-ramp artifacts.

This module reads existing CSV/JSON artifacts only. It does not run or alter the
solver, boundary conditions, numerical flux, or acceptance logic.
"""

from __future__ import annotations

import argparse
import csv
from io import BytesIO
import json
from pathlib import Path
