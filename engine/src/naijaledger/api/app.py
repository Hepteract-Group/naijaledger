from fastapi import FastAPI

from naijaledger import __version__

app = FastAPI(
    title="NaijaLedger API",
    version=__version__,
    description="Civic accountability data platform for Nigeria",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "naijaledger-engine", "version": __version__}
