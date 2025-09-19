"""Configuration for OMERO ISCC service."""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class ServiceConfig:
    """Configuration for OMERO ISCC service."""

    # OMERO connection settings
    host: str = "localhost"
    port: int = 4064
    username: str = "root"
    password: str = "omero"
    secure: bool = True

    # Service settings
    poll_interval: int = 60  # seconds between polls
    batch_size: int = 100  # max images per poll
    chunk_size: int = 1024 * 1024  # 1MB file chunks
    namespace: str = "org.iscc.omero.sum"

    # Logging
    log_level: str = "info"
    log_file: Optional[str] = None

    # Optional webhook for notifications
    webhook_url: Optional[str] = None

    # Retry settings
    max_retries: int = 3
    retry_delay: int = 5  # seconds

    @classmethod
    def from_file(cls, path: Path) -> "ServiceConfig":
        """Load configuration from JSON file.

        Args:
            path: Path to config file

        Returns:
            ServiceConfig instance
        """
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def from_env(cls) -> "ServiceConfig":
        """Load configuration from environment variables.

        Environment variables should be prefixed with OMERO_ISCC_

        Returns:
            ServiceConfig instance
        """
        config = cls()

        # Map environment variables to config fields
        env_map = {
            "OMERO_ISCC_HOST": "host",
            "OMERO_ISCC_PORT": "port",
            "OMERO_ISCC_USERNAME": "username",
            "OMERO_ISCC_PASSWORD": "password",
            "OMERO_ISCC_SECURE": "secure",
            "OMERO_ISCC_POLL_INTERVAL": "poll_interval",
            "OMERO_ISCC_BATCH_SIZE": "batch_size",
            "OMERO_ISCC_CHUNK_SIZE": "chunk_size",
            "OMERO_ISCC_NAMESPACE": "namespace",
            "OMERO_ISCC_LOG_LEVEL": "log_level",
            "OMERO_ISCC_LOG_FILE": "log_file",
            "OMERO_ISCC_WEBHOOK_URL": "webhook_url",
            "OMERO_ISCC_MAX_RETRIES": "max_retries",
            "OMERO_ISCC_RETRY_DELAY": "retry_delay",
        }

        for env_var, field in env_map.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert to appropriate type
                field_type = type(getattr(config, field))
                if field_type == bool:
                    value = value.lower() in ("true", "1", "yes")
                elif field_type == int:
                    value = int(value)
                setattr(config, field, value)

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Dictionary representation
        """
        return asdict(self)

    def save(self, path: Path):
        """Save configuration to JSON file.

        Args:
            path: Path to save file
        """
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


def load_config(config_path: Optional[Path] = None) -> ServiceConfig:
    """Load configuration from file or environment.

    Args:
        config_path: Optional path to config file

    Returns:
        ServiceConfig instance
    """
    # Priority: file > environment > defaults
    if config_path and config_path.exists():
        config = ServiceConfig.from_file(config_path)
    else:
        config = ServiceConfig.from_env()

    return config