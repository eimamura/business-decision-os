#!/usr/bin/env python3
"""Seed the database from data/sample/ CSVs (NOT ground_truth/).

Usage:
    uv run python scripts/seed_db.py

Reads data/sample/*.csv and inserts into the database.
"""
import asyncio

from packages.persistence.sample_data import seed_from_database_url


async def seed_db() -> None:
    summaries = await seed_from_database_url()
    for table in summaries:
        print(f"{table['table_name']}: {table['row_count']} rows")


if __name__ == "__main__":
    asyncio.run(seed_db())
