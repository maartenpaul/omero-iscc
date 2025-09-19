"""Monitor OMERO for new images and trigger ISCC processing."""

import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Set, Generator
from omero.gateway import BlitzGateway, ImageWrapper

logger = logging.getLogger(__name__)


class OmeroImageMonitor:
    """Monitor OMERO server for newly imported images."""

    def __init__(
        self,
        conn: BlitzGateway,
        poll_interval: int = 60,
        batch_size: int = 100,
        namespace: str = "org.iscc.omero.sum"
    ):
        """Initialize the OMERO image monitor.

        Args:
            conn: Active BlitzGateway connection
            poll_interval: Seconds between polls
            batch_size: Maximum images to process per poll
            namespace: Namespace for ISCC annotations
        """
        self.conn = conn
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.namespace = namespace
        self.last_check_time: Optional[datetime] = None
        self.processed_ids: Set[int] = set()
        self._running = False

    def get_new_images(self, since: Optional[datetime] = None) -> Generator[ImageWrapper, None, None]:
        """Get images imported since the specified time.

        Args:
            since: Get images imported after this time (None for most recent)

        Yields:
            ImageWrapper objects for new images
        """
        try:
            # Use timelineListImages to get recent images
            if since:
                # Convert to milliseconds timestamp for OMERO
                tfrom = int(since.timestamp() * 1000)
                tto = int(datetime.now().timestamp() * 1000)
                images = self.conn.timelineListImages(tfrom=tfrom, tto=tto)
            else:
                # Get most recent batch
                images = self.conn.timelineListImages()

            count = 0
            for image in images:
                if count >= self.batch_size:
                    break

                # Check if already has ISCC annotation
                if not self._has_iscc_annotation(image):
                    yield image
                    count += 1

        except Exception as e:
            logger.error(f"Error getting new images: {e}")

    def _has_iscc_annotation(self, image: ImageWrapper) -> bool:
        """Check if image already has ISCC annotation.

        Args:
            image: Image to check

        Returns:
            True if ISCC annotation exists
        """
        try:
            for ann in image.listAnnotations():
                if ann.getNs() == self.namespace:
                    # Check if it's a MapAnnotation with ISCC data
                    if hasattr(ann, 'getValue'):
                        values = ann.getValue()
                        for key, _ in values:
                            if key.startswith('iscc:'):
                                return True
        except Exception as e:
            logger.warning(f"Error checking annotations for image {image.getId()}: {e}")
        return False

    def poll_once(self) -> int:
        """Poll for new images once.

        Returns:
            Number of new images found
        """
        new_count = 0
        try:
            # Get images since last check
            since = self.last_check_time if self.last_check_time else None

            for image in self.get_new_images(since):
                image_id = image.getId()

                # Skip if already processed in this session
                if image_id in self.processed_ids:
                    continue

                logger.info(f"Found new image: {image.getName()} (ID: {image_id})")
                self.processed_ids.add(image_id)
                new_count += 1

                # Yield to processor callback
                if hasattr(self, '_process_callback') and self._process_callback:
                    try:
                        self._process_callback(image)
                    except Exception as e:
                        logger.error(f"Error processing image {image_id}: {e}")

            # Update last check time
            self.last_check_time = datetime.now()

        except Exception as e:
            logger.error(f"Error during poll: {e}")

        return new_count

    def run(self, process_callback=None):
        """Run the monitor continuously.

        Args:
            process_callback: Function to call for each new image
        """
        self._process_callback = process_callback
        self._running = True

        logger.info(f"Starting OMERO image monitor (poll interval: {self.poll_interval}s)")

        while self._running:
            try:
                # Poll for new images
                new_count = self.poll_once()
                if new_count > 0:
                    logger.info(f"Processed {new_count} new images")

                # Wait before next poll
                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Monitor interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in monitor loop: {e}")
                time.sleep(self.poll_interval)

    def stop(self):
        """Stop the monitor."""
        self._running = False
        logger.info("Stopping OMERO image monitor")