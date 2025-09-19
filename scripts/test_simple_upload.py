#!/usr/bin/env python3
"""Simple test to debug OMERO upload issues."""

import sys
from pathlib import Path
from omero.gateway import BlitzGateway
import omero
from omero.model import FilesetI, FilesetEntryI, UploadJobI, ChecksumAlgorithmI
import omero.rtypes as rtypes
import hashlib
import time


def simple_upload_test(file_path):
    """Test upload with minimal monitoring."""
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return False

    print(f"Connecting to OMERO...")
    conn = BlitzGateway("root", "omero", host="localhost", port=4064, secure=True)

    if not conn.connect():
        print("Failed to connect")
        return False

    try:
        client = conn.c
        mrepo = client.getManagedRepository()

        # Create a simple fileset
        fileset = FilesetI()
        upload_job = UploadJobI()
        fileset.linkJob(upload_job)

        # Add file to fileset
        entry = FilesetEntryI()
        entry.clientPath = rtypes.rstring(str(file_path))
        fileset.addFilesetEntry(entry)

        # Basic import settings
        settings = omero.grid.ImportSettings()
        settings.checksumAlgorithm = ChecksumAlgorithmI()
        settings.checksumAlgorithm.value = rtypes.rstring("SHA1-160")
        settings.doThumbnails = rtypes.rbool(True)
        settings.noStatsInfo = rtypes.rbool(False)

        print(f"Starting import for {file_path.name}...")

        # Start import
        proc = mrepo.importFileset(fileset, settings)

        try:
            # Upload file
            print("Uploading file...")
            uploader = proc.getUploader(0)

            with open(file_path, "rb") as f:
                data = f.read()
                uploader.write(data, 0, len(data))

            uploader.close()
            print(f"Upload complete ({len(data)} bytes)")

            # Calculate checksum
            sha1 = hashlib.sha1(data).hexdigest()
            print(f"Checksum: {sha1}")

            # Verify upload
            handle = proc.verifyUpload([sha1])
            print(f"Verify handle: {handle}")

            # Simple monitoring - just wait a bit and check if images appear
            print("Waiting for import to complete...")
            time.sleep(10)  # Wait 10 seconds

            # Check if any new images appeared
            print("Checking for new images...")
            images = list(conn.getObjects("Image"))
            print(f"Total images in OMERO: {len(images)}")

            for img in images:
                print(f"  Image: {img.getName()} (ID: {img.getId()})")

            return True

        finally:
            proc.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "testdata/xyc_tiles.czi"
    simple_upload_test(file_path)
