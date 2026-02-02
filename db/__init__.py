"""Database package for Group Message Scheduler."""

from .database import db, get_database, init_indexes

__all__ = ["db", "get_database", "init_indexes"]
