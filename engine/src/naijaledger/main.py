import uvicorn

from naijaledger.api.app import app
from naijaledger.config import load_settings


def run() -> None:
    settings = load_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    run()
