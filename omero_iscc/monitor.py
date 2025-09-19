"""Monitor OMERO for new images and trigger ISCC processing."""

import time
import logging
from typing import Set
from omero.gateway import BlitzGateway

logger = logging.getLogger(__name__)


class OmeroImageMonitor:
    """Monitor OMERO server for newly imported images."""

    def __init__(
        self,
        conn: BlitzGateway,
        poll_interval: int = 60,
        batch_size: int = 100,
        namespace: str = "org.iscc.omero.sum",
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
        self.processed_ids: Set[int] = set()
        self._running = False

    def _has_iscc_annotation(self, image) -> bool:
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
                    if hasattr(ann, "getValue"):
                        values = ann.getValue()
                        for key, _ in values:
                            if key.startswith("iscc:"):
                                return True
        except Exception as e:
            logger.warning(f"Error checking annotations for image {image.getId()}: {e}")
        return False

    def run(self, process_callback=None):
        """Run the monitor continuously.

        Args:
            process_callback: Function to call for each new image
        """
        self._process_callback = process_callback
        self._running = True

        logger.info(
            f"Starting OMERO image monitor (poll interval: {self.poll_interval}s)"
        )

        # On startup, scan all existing images to populate processed_ids
        logger.info("Initial scan for existing images with ISCC annotations...")
        initial_scan_count = 0
        for image in self.conn.getObjects("Image"):
            if self._has_iscc_annotation(image):
                self.processed_ids.add(image.getId())
                initial_scan_count += 1
        logger.info(f"Found {initial_scan_count} images with existing ISCC annotations")

        while self._running:
            try:
                logger.debug("Starting poll cycle")

                # Simple approach: get all images, check which ones need processing
                new_count = 0
                processed_in_cycle = 0

                try:
                    # Process images in batches to limit memory usage
                    for image in self.conn.getObjects("Image"):
                        image_id = image.getId()

                        # Skip if already processed in this session
                        if image_id in self.processed_ids:
                            continue

                        # Check if has ISCC annotation (double-check in case added externally)
                        if self._has_iscc_annotation(image):
                            logger.debug(
                                f"Image {image_id} has ISCC annotation (added externally?)"
                            )
                            self.processed_ids.add(image_id)
                            continue

                        # This is an unprocessed image - process it
                        logger.info(
                            f"Found unprocessed image: {image.getName()} (ID: {image_id})"
                        )
                        new_count += 1

                        if self._process_callback:
                            try:
                                self._process_callback(image)
                                self.processed_ids.add(image_id)
                                processed_in_cycle += 1
                                logger.info(f"Successfully processed image {image_id}")
                            except Exception as e:
                                logger.error(f"Error processing image {image_id}: {e}")

                        # Respect batch size limit
                        if processed_in_cycle >= self.batch_size:
                            logger.info(
                                f"Reached batch size limit ({self.batch_size}), will continue in next cycle"
                            )
                            break

                except Exception as e:
                    logger.error(f"Error during image polling: {e}", exc_info=True)

                if new_count > 0:
                    logger.info(
                        f"Processed {processed_in_cycle} of {new_count} unprocessed images"
                    )
                else:
                    logger.debug("No unprocessed images found")

                # Wait before next poll
                logger.debug(f"Sleeping for {self.poll_interval} seconds")
                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Monitor interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in monitor loop: {e}", exc_info=True)
                time.sleep(self.poll_interval)

    def stop(self):
        """Stop the monitor."""
        self._running = False
        logger.info("Stopping OMERO image monitor")
