from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from packages.optimization.replenishment import ReplenishmentOptimizer
from packages.optimization import OptimizationInput, OptimizationContext


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
            opt_input = OptimizationInput(**payload)
            ctx = OptimizationContext(db_session=session)
            optimizer = ReplenishmentOptimizer()
            result = await optimizer.run(opt_input, ctx)

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
