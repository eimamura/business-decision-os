#!/usr/bin/env python3
"""Seed the database from data/sample/ CSVs (NOT ground_truth/).

Usage:
    uv run python scripts/seed_db.py

Reads data/sample/*.csv and inserts into the database.
"""
import asyncio
import csv
from pathlib import Path
from uuid import uuid4


async def seed_db() -> None:
    raise NotImplementedError("Phase 1 — DATABASE_URL required")


if __name__ == "__main__":
    asyncio.run(seed_db())
