from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from revenue_leak_radar.router import router

app = FastAPI(
    title="Revenue Leak Radar",
    description="Revenue leakage analysis and review API for RevAI.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/revenue-leak-radar")


@app.get("/")
def home():
    return {"service": "Revenue Leak Radar", "status": "ok"}
