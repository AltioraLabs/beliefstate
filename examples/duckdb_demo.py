import asyncio
import tempfile
from pathlib import Path

from beliefstate.models import Belief
from beliefstate.store.duckdb import DuckDBStore


async def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "beliefs.duckdb"

        async with DuckDBStore(db_path=str(db_path)) as store:
            belief = Belief(
                subject="user",
                predicate="likes",
                value="Python",
                confidence=1.0,
                turn=1,
                source="demo",
                session_id="demo-session",
                embedding=[1.0, 0.0, 0.0],
            )
            await store.add_belief("demo-session", belief)
            results = await store.search_beliefs(
                "demo-session",
                [1.0, 0.1, 0.0],
                threshold=0.7,
                limit=1,
            )

        async with DuckDBStore(db_path=str(db_path)) as store:
            persisted = await store.get_beliefs("demo-session")

        print(f"search_results={len(results)}")
        print(f"top_result={results[0].value if results else ''}")
        print(f"persisted_beliefs={len(persisted)}")


if __name__ == "__main__":
    asyncio.run(main())
