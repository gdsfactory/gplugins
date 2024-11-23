"""Disable print statements for overly verbose simulators."""

from __future__ import annotations

import os
import sys


class DisablePrint:
    def __init__(self) -> None:
        self.output = sys.stdout

    def __enter__(self) -> DisablePrint:
        sys.stdout = open(os.devnull, "w")
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        sys.stdout = self.output
