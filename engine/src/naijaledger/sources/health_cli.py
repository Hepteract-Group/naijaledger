import logging

from naijaledger.db.connection import create_db_engine
from naijaledger.sources.health import run_health_monitor


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    engine = create_db_engine()
    with engine.connect() as connection, connection.begin():
        summary = run_health_monitor(connection)

    print(
        "Health monitor complete:",
        f"checked={summary['checked']}",
        f"healthy={summary['healthy']}",
        f"degraded={summary['degraded']}",
        f"down={summary['down']}",
        f"tls_expired={summary['tls_expired']}",
        f"alerts={summary['alerts']}",
    )
