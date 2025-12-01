"""Database base configuration and session management."""

from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import Pool

from ..config import PricingConfig

# Create declarative base
Base = declarative_base()

# Global engine and session factory
_engine = None
_SessionFactory = None


def get_engine(config: PricingConfig):
    """
    Get or create SQLAlchemy engine.

    Args:
        config: Pricing configuration with database settings

    Returns:
        SQLAlchemy engine instance
    """
    global _engine

    if _engine is None:
        if not config.database_url:
            raise ValueError("database_url is required in config")

        # Create engine with connection pooling
        _engine = create_engine(
            config.database_url,
            pool_size=config.pool_size,
            max_overflow=config.pool_max_overflow,
            echo=config.echo_sql,
            pool_pre_ping=True,  # Verify connections before using
        )

        # Set schema search path for PostgreSQL
        if config.database_url.startswith("postgresql"):
            @event.listens_for(_engine, "connect")
            def set_search_path(dbapi_connection, connection_record):
                """Set schema search path on connection."""
                if config.schema_name and config.schema_name != "public":
                    cursor = dbapi_connection.cursor()
                    cursor.execute(f"SET search_path TO {config.schema_name}, public")
                    cursor.close()

    return _engine


def get_session_factory(config: PricingConfig):
    """
    Get or create session factory.

    Args:
        config: Pricing configuration

    Returns:
        SQLAlchemy session factory
    """
    global _SessionFactory

    if _SessionFactory is None:
        engine = get_engine(config)
        _SessionFactory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )

    return _SessionFactory


def get_session(config: PricingConfig) -> Session:
    """
    Create a new database session.

    Args:
        config: Pricing configuration

    Returns:
        SQLAlchemy session instance
    """
    SessionFactory = get_session_factory(config)
    return SessionFactory()


@contextmanager
def session_scope(config: PricingConfig) -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.

    Usage:
        with session_scope(config) as session:
            # Do work with session
            session.add(obj)
            # Automatically commits on success, rolls back on error

    Args:
        config: Pricing configuration

    Yields:
        Database session
    """
    session = get_session(config)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(config: PricingConfig, drop_all: bool = False) -> None:
    """
    Initialize database tables.

    Args:
        config: Pricing configuration
        drop_all: If True, drop all tables before creating (WARNING: destructive!)
    """
    engine = get_engine(config)

    # Create schema if it doesn't exist (PostgreSQL only)
    if config.database_url.startswith("postgresql") and config.schema_name != "public":
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {config.schema_name}"))
            conn.commit()

    # Drop tables if requested
    if drop_all:
        Base.metadata.drop_all(bind=engine)

    # Create all tables
    Base.metadata.create_all(bind=engine)


def close_db() -> None:
    """
    Close database connections and clean up resources.

    Call this when shutting down your application.
    """
    global _engine, _SessionFactory

    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionFactory = None
