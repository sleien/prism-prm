"""Aggregate all API routers under /api."""

from fastapi import APIRouter

from app.api import auth, contacts, events, journal, summary

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(contacts.router)
api_router.include_router(events.router)
api_router.include_router(journal.router)
api_router.include_router(summary.router)
