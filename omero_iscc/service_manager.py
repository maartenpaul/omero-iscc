"""Service manager for OMERO ISCC-SUM background processing."""

import sys
import logging
import signal
import time
from pathlib import Path
from typing import Optional, Dict, Any
from omero.gateway import BlitzGateway

from .monitor import OmeroImageMonitor
from .processor import IsccImageProcessor
from .config import ServiceConfig

logger = logging.getLogger(__name__)


class IsccServiceManager:
    """Manage the OMERO ISCC service lifecycle."""

    def __init__(self, config: Optional[ServiceConfig] = None):
        """Initialize the service manager.

        Args:
            config: Service configuration (uses defaults if None)
        """
        self.config = config or ServiceConfig()
        self.conn: Optional[BlitzGateway] = None
        self.monitor: Optional[OmeroImageMonitor] = None
        self.processor: Optional[IsccImageProcessor] = None
        self._running = False
        self._setup_logging()
        self._setup_signal_handlers()

    def _setup_logging(self):
        """Configure logging for the service."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)

        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Set specific levels for our modules
        logging.getLogger("omero_iscc").setLevel(log_level)

        # Reduce noise from OMERO libraries if not in debug mode
        if log_level != logging.DEBUG:
            logging.getLogger("omero").setLevel(logging.WARNING)
            logging.getLogger("Blitz").setLevel(logging.WARNING)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def connect(self, suppress_errors=False) -> bool:
        """Establish connection to OMERO server.

        Args:
            suppress_errors: If True, suppress verbose error logs during connection

        Returns:
            True if connection successful
        """
        # Temporarily adjust logging levels if suppressing errors
        omero_loggers = []
        original_levels = {}

        if suppress_errors:
            # Suppress multiple OMERO-related loggers
            logger_names = [
                "omero.gateway",
                "omero",
                "omero.clients",
                "Ice",
                "Glacier2",
            ]
            for name in logger_names:
                logger_obj = logging.getLogger(name)
                omero_loggers.append(logger_obj)
                original_levels[name] = logger_obj.level
                logger_obj.setLevel(logging.CRITICAL)

        try:
            if not suppress_errors:
                logger.info(
                    f"Connecting to OMERO server at {self.config.host}:{self.config.port}"
                )

            self.conn = BlitzGateway(
                username=self.config.username,
                passwd=self.config.password,
                host=self.config.host,
                port=self.config.port,
                secure=self.config.secure,
            )

            if not self.conn.connect():
                if not suppress_errors:
                    logger.error("Failed to connect to OMERO server")
                return False

            logger.info("Successfully connected to OMERO server")

            # Get user info for logging
            user = self.conn.getUser()
            logger.info(f"Connected as: {user.getName()} (ID: {user.getId()})")

            return True

        except Exception as e:
            if not suppress_errors:
                logger.error(f"Connection error: {e}")
            return False
        finally:
            # Restore original logging levels
            if suppress_errors:
                for logger_name, logger_obj in zip(
                    original_levels.keys(), omero_loggers
                ):
                    logger_obj.setLevel(original_levels[logger_name])

    def disconnect(self):
        """Disconnect from OMERO server."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Disconnected from OMERO server")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.conn = None

    def initialize_components(self):
        """Initialize monitor and processor components."""
        if not self.conn:
            raise RuntimeError("Not connected to OMERO server")

        # Initialize processor
        self.processor = IsccImageProcessor(
            conn=self.conn,
            namespace=self.config.namespace,
            chunk_size=self.config.chunk_size,
        )

        # Initialize monitor
        self.monitor = OmeroImageMonitor(
            conn=self.conn,
            poll_interval=self.config.poll_interval,
            batch_size=self.config.batch_size,
            namespace=self.config.namespace,
        )

        logger.info("Service components initialized")

    def process_image_callback(self, image):
        """Callback for processing new images.

        Args:
            image: ImageWrapper object to process
        """
        if not self.processor:
            logger.error("Processor not initialized")
            return

        try:
            # Check if already processed
            existing_iscc = self.processor.get_iscc_for_image(image)
            if existing_iscc:
                logger.debug(
                    f"Image {image.getId()} already has ISCC: {existing_iscc.get('iscc:sum')}"
                )
                return

            # Process the image
            iscc_code = self.processor.process_image(image)

            if iscc_code:
                logger.info(
                    f"Successfully processed image {image.getId()}: {iscc_code}"
                )

                # Optional: Send notification or update external system
                if self.config.webhook_url:
                    self._send_webhook_notification(image, iscc_code)
            else:
                logger.warning(f"Failed to generate ISCC for image {image.getId()}")

        except Exception as e:
            logger.error(f"Error in image callback: {e}", exc_info=True)

    def _send_webhook_notification(self, image, iscc_code: str):
        """Send webhook notification for processed image.

        Args:
            image: Processed image
            iscc_code: Generated ISCC code
        """
        try:
            import requests

            payload = {
                "event": "iscc_generated",
                "image_id": image.getId(),
                "image_name": image.getName(),
                "iscc_code": iscc_code,
                "timestamp": time.time(),
            }

            response = requests.post(self.config.webhook_url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.debug(f"Webhook notification sent for image {image.getId()}")
            else:
                logger.warning(f"Webhook returned status {response.status_code}")

        except Exception as e:
            logger.warning(f"Failed to send webhook notification: {e}")

    def run(self):
        """Run the service continuously."""
        logger.info("Starting OMERO ISCC Service")
        self._running = True

        # Connect to OMERO with retries
        max_retries = 30
        retry_delay = 2
        for attempt in range(max_retries):
            # Suppress errors for all but first and last attempts
            suppress = attempt > 0 and attempt < max_retries - 1
            if self.connect(suppress_errors=suppress):
                break
            if attempt < max_retries - 1:
                if attempt == 0:
                    logger.info(f"OMERO server not ready, will retry connection...")
                else:
                    logger.info(
                        f"Connection attempt {attempt + 1}/{max_retries} failed, retrying in {retry_delay}s..."
                    )
                time.sleep(retry_delay)
                retry_delay = min(
                    retry_delay * 1.5, 30
                )  # Exponential backoff with max 30s
            else:
                logger.error("Failed to connect after all retries, exiting")
                return

        try:
            # Initialize components
            self.initialize_components()

            # Start monitoring
            logger.info("Starting image monitoring")
            self.monitor._process_callback = self.process_image_callback

            # Run monitor (blocks until stopped)
            self.monitor.run(process_callback=self.process_image_callback)

        except KeyboardInterrupt:
            logger.info("Service interrupted by user")
        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Stop the service gracefully."""
        logger.info("Stopping OMERO ISCC Service")
        self._running = False

        if self.monitor:
            self.monitor.stop()

        self.disconnect()
        logger.info("Service stopped")

    def status(self) -> Dict[str, Any]:
        """Get service status.

        Returns:
            Dictionary with status information
        """
        return {
            "running": self._running,
            "connected": self.conn is not None and self.conn.isConnected(),
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "poll_interval": self.config.poll_interval,
                "namespace": self.config.namespace,
            },
            "monitor": {
                "active": self.monitor is not None,
                "last_check": self.monitor.last_check_time.isoformat()
                if self.monitor and self.monitor.last_check_time
                else None,
                "processed_count": len(self.monitor.processed_ids)
                if self.monitor
                else 0,
            },
        }


def main():
    """Main entry point for the service."""
    import argparse

    parser = argparse.ArgumentParser(description="OMERO ISCC-SUM Service")
    parser.add_argument("--config", type=Path, help="Path to configuration file")
    parser.add_argument("--host", help="OMERO server host")
    parser.add_argument("--port", type=int, help="OMERO server port")
    parser.add_argument("--username", help="OMERO username")
    parser.add_argument("--password", help="OMERO password")
    parser.add_argument("--poll-interval", type=int, help="Poll interval in seconds")
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        help="Logging level",
    )
    parser.add_argument(
        "--once", action="store_true", help="Run once and exit (for testing)"
    )

    args = parser.parse_args()

    # Load configuration
    if args.config and args.config.exists():
        config = ServiceConfig.from_file(args.config)
    else:
        config = ServiceConfig.from_env()

    # Override with command-line arguments
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.username:
        config.username = args.username
    if args.password:
        config.password = args.password
    if args.poll_interval:
        config.poll_interval = args.poll_interval
    if args.log_level:
        config.log_level = args.log_level

    # Create and run service
    service = IsccServiceManager(config)

    # Always run continuously (remove --once option functionality for now)
    service.run()


if __name__ == "__main__":
    main()
