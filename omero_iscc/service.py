"""Simplified OMERO ISCC service - single module implementation."""

import os
import time
import json
import logging
from pathlib import Path
from typing import Dict, Optional
import omero
from omero.rtypes import rlong
from omero.gateway import BlitzGateway, ImageWrapper, MapAnnotationWrapper
from iscc_sum import IsccSumProcessor, IsccSumResult

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
OMERO_HOST = os.getenv("OMERO_ISCC_HOST", "localhost")
OMERO_USER = os.getenv("OMERO_ISCC_USER", "root")
OMERO_PWD = os.getenv("OMERO_ISCC_PASSWORD", "omero")
POLL_SECONDS = int(os.getenv("OMERO_ISCC_POLL_SECONDS", "5"))
PERSIST_DIR = os.getenv("OMERO_ISCC_PERSIST_DIR", "/data")
NAMESPACE = "org.iscc.omero.sum"

# Global objects
conn: Optional[BlitzGateway] = None
seen: Dict[
    str, IsccSumResult
] = {}  # file_hash -> IsccSumResult cache (memory only, not persisted)
last_image_id: int = 0  # Last processed image ID (persisted across restarts)


def load_state():
    """Load persisted state (last_image_id only)."""
    global last_image_id

    state_file = Path(PERSIST_DIR) / "iscc_service_state.json"
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                last_image_id = state.get("last_image_id", 0)
                logger.info(f"Loaded state: last_image_id={last_image_id}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            last_image_id = 0
    else:
        last_image_id = 0


def save_state():
    """Persist current state (last_image_id only)."""
    state_file = Path(PERSIST_DIR) / "iscc_service_state.json"
    try:
        state = {"last_image_id": last_image_id}

        # Ensure directory exists
        state_file.parent.mkdir(parents=True, exist_ok=True)

        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved state: last_image_id={last_image_id}")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def connect_omero() -> bool:
    """Connect to OMERO server."""
    global conn

    try:
        logger.info(f"Connecting to OMERO at {OMERO_HOST}:4064")
        conn = BlitzGateway(
            username=OMERO_USER,
            passwd=OMERO_PWD,
            host=OMERO_HOST,
            port=4064,
            secure=True,
        )

        if not conn.connect():
            logger.error("Failed to connect to OMERO")
            return False

        # Set to cross-group querying
        # conn.SERVICE_OPTS.setOmeroGroup("-1")

        user = conn.getUser()
        logger.info(f"Connected as {user.getName()} (ID: {user.getId()})")
        return True

    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False


def process_image(image: ImageWrapper):
    """Process a single image to generate and store ISCC."""
    global seen, last_image_id

    image_id = image.getId()
    image_name = image.getName()

    try:
        logger.info(f"Processing image {image_id}: {image_name}")

        # Check if already has ISCC annotation
        for ann in image.listAnnotations():
            if ann.getNs() == NAMESPACE:
                logger.debug(f"Image {image_id} already has ISCC annotation, skipping")
                last_image_id = image_id
                save_state()
                return

        # Get original files
        orig_files = list(image.getImportedImageFiles())
        if not orig_files:
            logger.warning(f"No original files for image {image_id}")
            last_image_id = image_id
            save_state()
            return

        # Process first original file
        orig_file = orig_files[0]
        file_hash = orig_file.getHash()

        # Check in-memory cache (reduces redundant processing within same session)
        if file_hash in seen:
            logger.info(f"Using cached ISCC for hash {file_hash}")
            result = seen[file_hash]
        else:
            # Generate ISCC from file data
            logger.debug(
                f"Generating ISCC for {orig_file.getName()} ({orig_file.getSize()} bytes)"
            )
            hasher = IsccSumProcessor()

            # Stream file in chunks using simpler API
            file_size = orig_file.getSize()
            bytes_processed = 0

            for chunk in orig_file.getFileInChunks():
                hasher.update(chunk)
                bytes_processed += len(chunk)

                # Log progress for large files (every 10MB)
                if file_size > 10 * 1024 * 1024 and bytes_processed % (
                    10 * 1024 * 1024
                ) < len(chunk):
                    progress = int((bytes_processed / file_size) * 100)
                    logger.debug(f"Progress: {progress}%")

            # Get result
            result = hasher.result(wide=True, add_units=True)
            seen[file_hash] = result
            logger.info(f"Generated ISCC: {result.iscc}")

        # Store as annotation
        map_ann = MapAnnotationWrapper(conn)
        map_ann.setNs(NAMESPACE)

        # Store ISCC codes
        annotation_data = [["iscc:sum", result.iscc]]
        if hasattr(result, "units") and result.units:
            if len(result.units) > 0:
                annotation_data.append(["iscc:data", result.units[0]])
            if len(result.units) > 1:
                annotation_data.append(["iscc:inst", result.units[1]])

        map_ann.setValue(annotation_data)
        map_ann.save()
        image.linkAnnotation(map_ann)

        logger.info(f"Stored ISCC annotation for image {image_id}")

    except Exception as e:
        logger.error(f"Error processing image {image_id}: {e}", exc_info=True)

    # Always update last_image_id
    last_image_id = image_id
    save_state()


def run():
    """Main service loop."""
    global last_image_id, seen

    logger.info("Starting OMERO ISCC Service")

    # Load persisted state (last_image_id only)
    load_state()
    # Initialize in-memory cache (not persisted)
    seen = {}

    # Connect with retries
    max_retries = 30
    retry_delay = 2
    for attempt in range(max_retries):
        if connect_omero():
            break
        if attempt < max_retries - 1:
            logger.info(f"Retry {attempt + 1}/{max_retries} in {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, 30)
        else:
            logger.error("Failed to connect after all retries")
            return

    logger.info(f"Starting main loop (poll every {POLL_SECONDS}s)")

    # Main loop
    while True:
        try:
            # Get images with ID greater than last_image_id using HQL
            images_processed = 0

            # Use HQL query to efficiently get only images with ID > last_image_id
            query_service = conn.getQueryService()
            hql_query = "SELECT i FROM Image i WHERE i.id > :minId ORDER BY i.id"
            params = omero.sys.ParametersI()
            params.addLong("minId", last_image_id)
            params.page(0, 100)  # Limit to 100 images per iteration

            images_raw = query_service.findAllByQuery(hql_query, params, conn.SERVICE_OPTS)

            if not images_raw:
                logger.debug("No new images found")
            else:
                # Wrap raw objects with ImageWrapper for easier access
                for img_raw in images_raw:
                    image = ImageWrapper(conn, img_raw)
                    process_image(image)
                    images_processed += 1

                logger.info(
                    f"Iteration complete: processed {images_processed} images, cache size: {len(seen)}"
                )

            # Wait before next iteration
            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            logger.info("Service interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(POLL_SECONDS)

    # Cleanup
    if conn:
        conn.close()
    logger.info("Service stopped")


if __name__ == "__main__":
    run()
