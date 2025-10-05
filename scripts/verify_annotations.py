#!/usr/bin/env python
"""Verify ISCC annotations on OMERO images."""

import os
from omero.gateway import BlitzGateway

# Connection parameters
HOST = os.getenv("OMERO_HOST", "localhost")
USER = os.getenv("OMERO_USER", "root")
PASSWORD = os.getenv("OMERO_PASSWORD", "omero")
NAMESPACE = "org.iscc.omero"

# Connect to OMERO
conn = BlitzGateway(username=USER, passwd=PASSWORD, host=HOST, port=4064, secure=True)
if not conn.connect():
    print("Failed to connect to OMERO")
    exit(1)

print(f"Connected as {conn.getUser().getName()}")
conn.SERVICE_OPTS.setOmeroGroup(-1)  # View all groups

# Get all images
images = list(conn.getObjects("Image"))
print(f"\nFound {len(images)} images:")

for img in images:
    print(f"\n  Image {img.getId()}: {img.getName()}")

    # Check for ISCC annotations
    found_iscc = False
    for ann in img.listAnnotations():
        # Show all annotations for debugging
        ann_ns = ann.getNs() if ann.getNs() else "NO_NAMESPACE"
        print(f"    Found annotation with namespace: {ann_ns}")

        if ann.getNs() == NAMESPACE:
            found_iscc = True
            print(f"    ✓ Has ISCC annotation:")

            # Show the key-value pairs
            if hasattr(ann, "getValue"):
                for key, value in ann.getValue():
                    print(f"      - {key}: {value}")

    if not found_iscc:
        print(f"    ✗ No ISCC annotation")

conn.close()
print("\nDone!")
