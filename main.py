from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import passports
from app.services.geospatial import initialize_earth_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs when the server starts
    print("Initializing Google Earth Engine...")
    initialize_earth_engine()
    print("Earth Engine Online.")
    yield
    # This runs when the server shuts down
    print("Shutting down Earth-Y Engine...")

app = FastAPI(title="Earth-Y Engine API", lifespan=lifespan)

# =====================================================================
# CORS configuration (The Bridge)
# =====================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",                     # Local development
        "https://earth-y-final-version.vercel.app"   # Live Vercel frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(passports.router, prefix="/api/v1/passports", tags=["Passports"])

@app.get("/")
def read_root():
    return {"status": "Engine Operational", "service": "Earth-Y Core"}