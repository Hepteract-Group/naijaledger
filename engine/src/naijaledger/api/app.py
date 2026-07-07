from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from naijaledger import __version__
from naijaledger.config import load_settings

app = FastAPI(
    title="NaijaLedger API",
    version=__version__,
    description="Civic accountability data platform for Nigeria",
)

_settings = load_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "naijaledger-engine", "version": __version__}
