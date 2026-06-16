"""Aggregate all API routers under /api."""

from fastapi import APIRouter

from app.api import auth, contacts, events

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(contacts.router)
api_router.include_router(events.router)
