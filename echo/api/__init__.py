"""API routers."""

from .agent import router as agent_router
from .clips import router as clips_router
from .search import router as search_router
from .status import router as status_router

ROUTERS = [status_router, clips_router, search_router, agent_router]
