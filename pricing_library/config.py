"""Configuration for the pricing library."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PricingConfig:
    """
    Configuration for the pricing library.

    Attributes:
        use_database: Whether to use database persistence (default: False for backward compatibility)
        database_url: Database connection URL (e.g., "postgresql://user:pass@localhost/db")
        entity_type: The type of entity to track (e.g., "user", "family", "team", "organization")
        schema_name: Database schema name (default: "public")
        enable_credit_expiration: Whether to enable credit expiration (default: False)
        pool_size: Database connection pool size (default: 5)
        pool_max_overflow: Maximum overflow connections (default: 10)
        echo_sql: Whether to echo SQL statements (useful for debugging, default: False)
    """

    use_database: bool = False
    database_url: Optional[str] = None
    entity_type: str = "user"
    schema_name: str = "public"
    enable_credit_expiration: bool = False
    pool_size: int = 5
    pool_max_overflow: int = 10
    echo_sql: bool = False

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.use_database and not self.database_url:
            raise ValueError("database_url must be provided when use_database=True")

        # Validate entity_type
        valid_entity_types = ["user", "family", "team", "organization", "tenant"]
        if self.entity_type not in valid_entity_types:
            # Allow custom entity types, but warn if not in common list
            import warnings
            warnings.warn(
                f"Using custom entity_type '{self.entity_type}'. "
                f"Common types are: {', '.join(valid_entity_types)}"
            )

    @classmethod
    def for_database(
        cls,
        database_url: str,
        entity_type: str = "user",
        **kwargs
    ) -> "PricingConfig":
        """
        Create a configuration for database mode.

        Args:
            database_url: Database connection URL
            entity_type: The type of entity to track
            **kwargs: Additional configuration options

        Returns:
            PricingConfig instance configured for database mode
        """
        return cls(
            use_database=True,
            database_url=database_url,
            entity_type=entity_type,
            **kwargs
        )

    @classmethod
    def for_memory(cls, entity_type: str = "user") -> "PricingConfig":
        """
        Create a configuration for in-memory mode.

        Args:
            entity_type: The type of entity to track

        Returns:
            PricingConfig instance configured for in-memory mode
        """
        return cls(
            use_database=False,
            entity_type=entity_type,
        )
