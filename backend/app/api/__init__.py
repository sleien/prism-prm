"""Aggregate all API routers under /api."""

from fastapi import APIRouter

from app.api import auth, contacts, enrichment, events, journal, sharing, summary

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(contacts.router)
api_router.include_router(enrichment.router)
api_router.include_router(events.router)
api_router.include_router(journal.router)
api_router.include_router(sharing.router)
api_router.include_router(summary.router)
