from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from packages.simulation import SimulationContext, SimulationInput
from packages.simulation.inventory import InventorySimulator


async def main() -> None:
    job_run_id = UUID(os.environ["JOB_RUN_ID"])
    database_url = os.environ["DATABASE_URL"]
    payload = json.loads(os.environ.get("JOB_PAYLOAD", "{}"))

    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await session.execute(
            text("UPDATE job_runs SET status='running', started_at=:now WHERE id=:id"),
            {"now": datetime.now(timezone.utc), "id": str(job_run_id)},
        )
        await session.commit()

        try:
            sim_input = SimulationInput(**payload)
            ctx = SimulationContext(db_session=session)
            simulator = InventorySimulator()
            result = await simulator.run(sim_input, ctx)

            await session.execute(
                text(
                    "UPDATE job_runs SET status='succeeded', output_json=:output, "
                    "completed_at=:now WHERE id=:id"
                ),
                {
                    "output": json.dumps(result.model_dump()),
                    "now": datetime.now(timezone.utc),
                    "id": str(job_run_id),
                },
            )
            await session.commit()
        except Exception as exc:
            await session.execute(
                text(
                    "UPDATE job_runs SET status='failed', error_message=:err, "
                    "completed_at=:now WHERE id=:id"
                ),
                {
                    "err": str(exc),
                    "now": datetime.now(timezone.utc),
                    "id": str(job_run_id),
                },
            )
            await session.commit()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
