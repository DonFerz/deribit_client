"""Сборка всех роутеров API v1."""

from fastapi import APIRouter

from app.api.v1.prices import router as prices_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(prices_router)
