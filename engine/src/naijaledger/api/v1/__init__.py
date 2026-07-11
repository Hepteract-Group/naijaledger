from fastapi import APIRouter

from naijaledger.api.v1 import (
    awards,
    contracts,
    export,
    facets,
    flags,
    graph,
    map_states,
    parties,
    sources,
    tenders,
)

router = APIRouter()
router.include_router(sources.router)
router.include_router(parties.router)
router.include_router(tenders.router)
router.include_router(awards.router)
router.include_router(contracts.router)
router.include_router(flags.router)
router.include_router(facets.router)
router.include_router(map_states.router)
router.include_router(graph.router)
router.include_router(export.router)
