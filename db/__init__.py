"""Database package for Group Message Scheduler."""

from .database import db, get_database, init_indexes, init_database

__all__ = ["db", "get_database", "init_indexes", "init_database"]
