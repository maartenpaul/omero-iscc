"""Simplified OMERO ISCC service - single module implementation."""

import os
import time
import json
import logging
from pathlib import Path
from typing import Dict, Optional
import omero
from omero.gateway import BlitzGateway, ImageWrapper, MapAnnotationWrapper
from omero_iscc.biocode import biocode, declare

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
OMERO_HOST = os.getenv("OMERO_ISCC_HOST", "localhost")
OMERO_USER = os.getenv("OMERO_ISCC_USER", "root")
OMERO_PWD = os.getenv("OMERO_ISCC_PASSWORD", "omero")
POLL_SECONDS = int(os.getenv("OMERO_ISCC_POLL_SECONDS", "5"))
PERSIST_DIR = os.getenv("OMERO_ISCC_PERSIST_DIR", "/data")
RESET_STATE = os.getenv("OMERO_ISCC_RESET_STATE", "false").lower() == "true"
NAMESPACE = "org.iscc.omero"

# Global objects
conn: Optional[BlitzGateway] = None
seen: Dict[str, dict] = {}  # image_id -> iscc_note cache (memory only, not persisted)
last_image_id: int = 0  # Last processed image ID (persisted across restarts)


def load_state():
    """Load persisted state (last_image_id only)."""
    global last_image_id

    if RESET_STATE:
        logger.info("RESET_STATE is true, starting from image ID 0")
        last_image_id = 0
        return

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

        # Set to cross-group querying to see images across all groups
        conn.SERVICE_OPTS.setOmeroGroup(-1)

        user = conn.getUser()
        current_group = conn.getGroupFromContext()
        logger.info(f"Connected as {user.getName()} (ID: {user.getId()})")
        logger.info(
            f"Working in group: {current_group.getName() if current_group else 'All groups'} (ID: {current_group.getId() if current_group else -1})"
        )
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

        # Check in-memory cache (reduces redundant processing within same session)
        if image_id in seen:
            logger.info(f"Using cached ISCC for image {image_id}")
            iscc_note = seen[image_id]
        else:
            # Generate ISCC biocode from image planes
            logger.debug(f"Generating ISCC biocode for image {image_id}")

            # Get fresh image object with loaded pixels data
            image_with_pixels = conn.getObject("Image", image_id)

            iscc_note = biocode(conn, image_with_pixels)
            seen[image_id] = iscc_note
            logger.info(f"Generated ISCC-CODE: {iscc_note['iscc_code']}")

        # Declare to ISCC-HUB and get ISCC-ID
        iscc_id = declare(iscc_note, image_id)

        # Switch to the image's group for saving annotation
        group_id = image.getDetails().getGroup().getId()
        conn.SERVICE_OPTS.setOmeroGroup(group_id)

        # Store as annotation
        map_ann = MapAnnotationWrapper(conn)
        map_ann.setNs(NAMESPACE)

        # Store ISCC-CODE and ISCC-ID
        annotation_data = [["ISCC-CODE", iscc_note["iscc_code"]]]
        if iscc_id:
            annotation_data.append(["ISCC-ID", iscc_id])
            logger.info(f"Received ISCC-ID: {iscc_id}")

        map_ann.setValue(annotation_data)
        map_ann.save()
        image.linkAnnotation(map_ann)

        # Switch back to all groups for next query
        conn.SERVICE_OPTS.setOmeroGroup(-1)

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

            logger.debug(f"Querying for images with ID > {last_image_id}")

            # Use HQL query to efficiently get only images with ID > last_image_id
            query_service = conn.getQueryService()
            hql_query = "SELECT i FROM Image i WHERE i.id > :minId ORDER BY i.id"
            params = omero.sys.ParametersI()
            params.addLong("minId", last_image_id)
            params.page(0, 100)  # Limit to 100 images per iteration

            logger.debug(f"Executing HQL query: {hql_query}")

            images_raw = query_service.findAllByQuery(
                hql_query, params, conn.SERVICE_OPTS
            )

            logger.debug(
                f"Query returned {len(images_raw) if images_raw else 0} images"
            )

            if not images_raw:
                logger.debug(f"No new images found with ID > {last_image_id}")

                # In debug mode, also check total image count and list all IDs
                if logger.isEnabledFor(logging.DEBUG):
                    count_query = "SELECT COUNT(i) FROM Image i"
                    count_result = query_service.projection(
                        count_query, None, conn.SERVICE_OPTS
                    )
                    total_images = count_result[0][0].val if count_result else 0
                    logger.debug(f"Total images in database: {total_images}")

                    # List all image IDs for debugging
                    id_query = "SELECT i.id FROM Image i ORDER BY i.id"
                    id_result = query_service.projection(
                        id_query, None, conn.SERVICE_OPTS
                    )
                    if id_result:
                        image_ids = [r[0].val for r in id_result]
                        logger.debug(f"All image IDs in database: {image_ids}")
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
