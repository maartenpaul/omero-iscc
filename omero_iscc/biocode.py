# -*- coding: utf-8 -*-
from datetime import datetime, timezone
import os
import requests
from omero_iscc.imagewalk import iter_planes_blitz_image, Plane
from iscc_sum import IsccSumProcessor
import iscc_crypto as icr
import numpy as np
import logging


logger = logging.getLogger(__name__)


def biocode(conn, image_obj):
    # type: (BlitzGateway, ImageWrapper | object) -> dict
    """
    Generate ISCC biocode for an OMERO image.

    Processes all planes of the image sequentially, generating a wide ISCC
    code with datahash and unit identifiers.

    :param conn: Active BlitzGateway connection to OMERO server
    :param image_obj: OMERO image (ImageWrapper or raw image object)
    :return: Dictionary with 'iscc_code', 'datahash', and 'units' keys
    """
    hasher = IsccSumProcessor()
    for plane in iter_planes_blitz_image(conn, image_obj):
        hasher.update(plane_to_bytes(plane))
    result = hasher.result(wide=True, add_units=True)
    iscc_note = {
        "iscc_code": result.iscc,
        "datahash": result.datahash,
        "units": [str(u) for u in result.units][:-1],
    }
    return iscc_note


def declare(iscc_note, image_id):
    # type: (dict, int) -> str | None
    """
    Submit ISCC declaration to ISCC-HUB and return ISCC-ID.

    Adds nonce, timestamp, and gateway URL to the ISCC note, signs it with
    the keypair from environment, and submits to ISCC-HUB. Handles both new
    declarations (200) and existing declarations (409).

    :param iscc_note: Dictionary with 'iscc_code', 'datahash', and 'units'
    :param image_id: OMERO image ID for gateway URL construction
    :return: ISCC-ID string if successful, None if configuration missing or request fails
    """
    try:
        keypair = icr.key_from_env()
    except Exception as e:
        logger.info(f"Failed to load keypair: {e}")
        return

    hub_id = os.getenv("ISCC_HUB_ID", None)
    hub_url = os.getenv("ISCC_HUB_URL", None)
    omero_host_url = os.getenv("OMERO_HOST_PUBLIC_URL", None)
    if not all([hub_id, hub_url, omero_host_url]):
        logger.info(
            "OMERO_HOST_PUBLIC_URL, ISCC_HUB_ID, ISCC_HUB_URL must be set to declare ISCC."
        )
        return

    iscc_note["nonce"] = icr.create_nonce(int(os.getenv("ISCC_HUB_ID", 0)))
    iscc_note["timestamp"] = timestamp()
    iscc_note["gateway"] = f"{omero_host_url}/webclient/?show=image-{image_id}"
    signed_note = icr.sign_json(iscc_note, keypair)
    endpoint = hub_url.removesuffix("/") + "/declaration"
    try:
        response = requests.post(endpoint, json=signed_note)
    except Exception as e:
        logger.info(f"Failed to submit declaration: {e}")
        return

    # Handle existing declaration
    if response.status_code == 409:
        try:
            error_data = response.json().get("error", {})
            existing_iscc_id = error_data.get("existing_iscc_id")
            if existing_iscc_id:
                return existing_iscc_id
        except Exception as e:
            logger.warning(f"Failed to parse 409 response: {e}")

    # Success - extract new ISCC-ID from response
    try:
        iscc_id = response.json()["credentialSubject"]["declaration"]["iscc_id"]
        return iscc_id
    except (KeyError, ValueError) as e:
        logger.warning(f"Invalid ISCC-HUB response format: {str(e)}")


def timestamp():
    # type: () -> str
    """
    Create RFC 3339 formatted timestamp in UTC with millisecond precision.

    :return: ISO 8601 timestamp string (e.g., '2025-10-05T14:23:45.123Z')
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def plane_to_bytes(plane):
    # type: (Plane) -> bytes
    """
    Convert a 2D plane to canonical big-endian byte representation.

    Flattens the plane in C-order (row-major: Y then X) and converts to
    big-endian bytes for compatibility with OMERO and ISCC processing.

    :param plane: Plane object with xy_array attribute (2D NumPy array)
    :return: Big-endian bytes of flattened plane data
    :raises ValueError: If plane is not 2D
    """
    if plane.xy_array.ndim != 2:
        raise ValueError(f"Expected 2D plane, got {plane.ndim}D")

    # Flatten plane in C-order (row-major: Y then X)
    flat = plane.xy_array.flatten(order="C")

    # Use numpy's tobytes() with explicit big-endian conversion
    # This is MUCH faster than struct.pack for large arrays
    if flat.dtype.byteorder == ">" or (
        flat.dtype.byteorder == "=" and np.little_endian
    ):
        # Already big-endian or need to swap
        canonical_bytes = flat.astype(f">{flat.dtype.char}", copy=False).tobytes()
    else:
        # Convert to big-endian
        canonical_bytes = flat.astype(f">{flat.dtype.char}").tobytes()

    return canonical_bytes
