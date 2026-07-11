from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from naijaledger import __version__
from naijaledger.api.rate_limit import build_rate_limit_middleware, create_fixed_window_limiter
from naijaledger.api.v1 import router as v1_router
from naijaledger.api.versioning import build_api_version_middleware
from naijaledger.config import Settings, load_settings

PUBLIC_API_DESCRIPTION = """
NaijaLedger public read API for Nigerian civic-accountability data
(public finance transparency).

**Versioning:** URL path `/v1` is the stable contract. Additive fields and new GET routes
may appear without a bump; breaking changes require `/v2`. Response header `API-Version: 1`
mirrors the contract major. OpenAPI `info.version` is the engine *package* version, not the
API contract major.

**Flags:** Anomaly flags are **hypotheses, not verified claims**. They are never presented as
proven wrongdoing. Treat `evidence` as investigative leads pending human review.
""".strip()

OPENAPI_TAGS = [
    {"name": "sources", "description": "Registered public data sources"},
    {"name": "parties", "description": "Canonical agencies, companies, and persons"},
    {"name": "tenders", "description": "Procurement tenders"},
    {"name": "awards", "description": "Awards linked to tenders"},
    {"name": "contracts", "description": "Contracts linked to awards"},
    {
        "name": "flags",
        "description": "Open anomaly flag hypotheses (not verified claims)",
    },
    {
        "name": "facets",
        "description": "Distinct state / LGA / year values for Explore drill-down",
    },
    {
        "name": "export",
        "description": ("Partner bulk export (bearer token required). Flags remain hypotheses."),
    },
]


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings if settings is not None else load_settings()
    application = FastAPI(
        title="NaijaLedger Public API",
        version=__version__,
        description=PUBLIC_API_DESCRIPTION,
        license_info={"name": "See repository LICENSE"},
        openapi_tags=OPENAPI_TAGS,
    )

    application.include_router(v1_router, prefix="/v1")
    application.state.partner_export_tokens = list(cfg.api_partner_export_tokens)
    application.state.partner_export_take = create_fixed_window_limiter(
        limit=cfg.api_partner_export_per_minute,
        max_keys=cfg.api_rate_limit_max_keys,
    )

    @application.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "naijaledger-engine", "version": __version__}

    # add_middleware: last registered runs first (outermost).
    # Order: CORS → api_version → rate_limit → routes (version wraps 429s).
    application.add_middleware(
        build_rate_limit_middleware(
            enabled=cfg.api_rate_limit_enabled,
            limit=cfg.api_rate_limit_per_minute,
            max_keys=cfg.api_rate_limit_max_keys,
            trust_forwarded_for=cfg.api_trust_forwarded_for,
        )  # type: ignore[arg-type]
    )
    application.add_middleware(build_api_version_middleware())  # type: ignore[arg-type]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.api_cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return application


app = create_app()
