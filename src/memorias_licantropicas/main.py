"""Ponto de entrada da API do jogo."""

from fastapi import FastAPI

app = FastAPI(
    title="Memórias Licantropicas",
    description="API de um jogo de investigação e dedução social.",
    version="0.1.0",
)


@app.get("/")
def index() -> dict[str, str]:
    return {"name": "Memórias Licantropicas", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
