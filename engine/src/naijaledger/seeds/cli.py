from naijaledger.db.connection import create_db_engine
from naijaledger.seeds.run import apply_seed_catalog


def run() -> None:
    engine = create_db_engine()
    with engine.connect() as connection, connection.begin():
        summary = apply_seed_catalog(connection)

    print(
        "Seed complete:",
        f"created={summary['created']}",
        f"skipped={summary['skipped']}",
        f"approved={summary['approved']}",
        f"corrected={summary['corrected']}",
        f"retired={summary['retired']}",
    )
