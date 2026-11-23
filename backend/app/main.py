"""Punto de entrada de AgroTerminalArgentina."""

from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="AgroTerminalArgentina",
    description="De los datos a las decisiones.",
    version="0.1.0",
)

app.include_router(api_router)
