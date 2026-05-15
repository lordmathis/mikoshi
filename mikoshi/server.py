import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mikoshi.lifespan import lifespan
from mikoshi.middleware import InFlightMiddleware, InFlightRequests
from mikoshi.routes import register_routes
from mikoshi.webui import setup_webui
from mikoshi.workspace import WorkspaceError, WorkspaceNotFoundError

logger = logging.getLogger(__name__)

in_flight = InFlightRequests()

app = FastAPI(lifespan=lifespan)
app.state.in_flight = in_flight


@app.exception_handler(WorkspaceNotFoundError)
async def workspace_not_found_handler(request: Request, exc: WorkspaceNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(WorkspaceError)
async def workspace_error_handler(request: Request, exc: WorkspaceError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

app.add_middleware(InFlightMiddleware, tracker=in_flight)

# Configure CORS for web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],  # Vite default port and common dev port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
register_routes(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Serve static files from the web UI build (production)
setup_webui(app)
