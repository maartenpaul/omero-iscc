"""Upload a bio image file to OMERO server using ManagedRepository."""

import sys
import argparse
from pathlib import Path
from omero.gateway import BlitzGateway
import omero
from omero.model import FilesetI, FilesetEntryI, UploadJobI, ChecksumAlgorithmI
from omero.model import ProjectI, DatasetI, ProjectDatasetLinkI
import omero.rtypes as rtypes
import hashlib


def create_project_and_dataset(conn, project_name, dataset_name):
    """Create a new project and dataset in OMERO.

    Args:
        conn: BlitzGateway connection
        project_name: Name for the new project
        dataset_name: Name for the new dataset

    Returns:
        Tuple of (project_id, dataset_id)
    """
    # Create project
    project = ProjectI()
    project.setName(rtypes.rstring(project_name))
    project = conn.getUpdateService().saveAndReturnObject(project)
    project_id = project.getId().getValue()
    print(f"Created project '{project_name}' with ID: {project_id}")

    # Create dataset
    dataset = DatasetI()
    dataset.setName(rtypes.rstring(dataset_name))
    dataset = conn.getUpdateService().saveAndReturnObject(dataset)
    dataset_id = dataset.getId().getValue()
    print(f"Created dataset '{dataset_name}' with ID: {dataset_id}")

    # Link dataset to project
    link = ProjectDatasetLinkI()
    link.setParent(ProjectI(project_id, False))
    link.setChild(DatasetI(dataset_id, False))
    conn.getUpdateService().saveAndReturnObject(link)
    print(f"Linked dataset to project")

    return project_id, dataset_id


def calculate_sha1(file_path):
    """Calculate SHA1 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        SHA1 hash as hex string
    """
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
    return sha1.hexdigest()


def upload_to_managed_repository(conn, file_path, dataset_id=None):
    """Upload a file to OMERO's ManagedRepository and initiate import.

    Args:
        conn: BlitzGateway connection
        file_path: Path to the bio-image file
        dataset_id: Optional dataset ID to link the image to

    Returns:
        True if successful, False otherwise
    """
    file_path = Path(file_path)

    try:
        # Get the managed repository
        client = conn.c
        mrepo = client.getManagedRepository()

        # Create a fileset for the import
        fileset = FilesetI()
        upload_job = UploadJobI()
        fileset.linkJob(upload_job)

        # Add the file to the fileset
        entry = FilesetEntryI()
        entry.clientPath = rtypes.rstring(str(file_path))
        fileset.addFilesetEntry(entry)

        # Create import settings
        settings = omero.grid.ImportSettings()
        settings.checksumAlgorithm = ChecksumAlgorithmI()
        settings.checksumAlgorithm.value = rtypes.rstring("SHA1-160")

        # Important: Set the target dataset/project in settings
        if dataset_id:
            settings.doThumbnails = rtypes.rbool(True)
            settings.noStatsInfo = rtypes.rbool(False)
            # Set the dataset as target - use the dataset wrapper properly
            from omero.model import DatasetI

            target = DatasetI(dataset_id, False)
            settings.userSpecifiedTarget = target
            settings.userSpecifiedName = rtypes.rstring(file_path.name)

        print(f"Starting import process for {file_path.name}...")

        # Start the import process
        proc = mrepo.importFileset(fileset, settings)

        try:
            # Upload the file
            print(f"Uploading file content...")
            uploader = proc.getUploader(0)

            # Read and upload the file in chunks
            file_size = file_path.stat().st_size
            chunk_size = 1024 * 1024  # 1MB chunks
            bytes_uploaded = 0

            with open(file_path, "rb") as f:
                offset = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    uploader.write(chunk, offset, len(chunk))
                    offset += len(chunk)
                    bytes_uploaded += len(chunk)

                    # Progress indicator
                    progress = int((bytes_uploaded / file_size) * 100)
                    print(f"Upload progress: {progress}%", end="\r")

            print(f"\nUpload complete. Closing uploader...")
            uploader.close()

            # Calculate checksum for verification
            print("Calculating checksum...")
            checksum = calculate_sha1(file_path)

            # Verify the upload
            print("Verifying upload...")
            handle = proc.verifyUpload([checksum])

            # The handle can be used to monitor the import process
            print(f"Import initiated. Handle: {handle}")

            # Simple wait approach - the import will continue in background
            print("Waiting for server-side import to complete...")
            import time

            # Wait a reasonable time for import to complete
            time.sleep(10)  # Wait 10 seconds for processing

            # Check if any images were created
            print("Checking for newly imported images...")
            try:
                # Simple approach: check if new images appear
                images = list(conn.getObjects("Image"))
                if images:
                    # Show the most recent image(s)
                    recent_images = sorted(
                        images, key=lambda x: x.getId(), reverse=True
                    )[:3]
                    print(f"Recent images in OMERO:")
                    for img in recent_images:
                        print(f"  Image: {img.getName()} (ID: {img.getId()})")

                        # Check if this image is in our target dataset
                        if dataset_id:
                            dataset = conn.getObject("Dataset", dataset_id)
                            if dataset:
                                dataset_images = list(dataset.listChildren())
                                img_ids = [img.getId() for img in dataset_images]
                                if img.getId() in img_ids:
                                    print(
                                        f"    ✓ Linked to dataset '{dataset.getName()}' (ID: {dataset_id})"
                                    )
                                else:
                                    print(
                                        f"    ⚠ Not linked to target dataset - may be orphaned"
                                    )
                else:
                    print("No images found in OMERO")
            except Exception as e:
                print(f"Error checking for imported images: {e}")
                print(
                    "The import may still have succeeded - check OMERO.web to confirm."
                )

            return True

        finally:
            proc.close()

    except Exception as e:
        print(f"Error during upload: {e}")
        import traceback

        traceback.print_exc()
        return False


def import_bioimage(
    file_path,
    host="localhost",
    port=4064,
    username="root",
    password="omero",
    dataset_id=None,
    project_name=None,
    dataset_name=None,
):
    """Import a bio-image file to OMERO using ManagedRepository.

    Args:
        file_path: Path to the bio-image file
        host: OMERO server hostname
        port: OMERO server port
        username: OMERO username
        password: OMERO password
        dataset_id: Optional existing dataset ID to import into
        project_name: Name for new project (if dataset_id not provided)
        dataset_name: Name for new dataset (if dataset_id not provided)

    Returns:
        True if successful, False otherwise
    """
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return False

    print(f"Connecting to OMERO server at {host}:{port}...")
    conn = BlitzGateway(username, password, host=host, port=port, secure=True)

    if not conn.connect():
        print("Failed to connect to OMERO server")
        return False

    try:
        # If no dataset_id provided, create project/dataset
        if dataset_id is None and (project_name or dataset_name):
            project_name = project_name or "Imported Images"
            dataset_name = dataset_name or "Import Dataset"

            # Check if project already exists
            projects = list(
                conn.getObjects("Project", attributes={"name": project_name})
            )
            if projects:
                project = projects[0]
                project_id = project.getId()
                print(f"Using existing project '{project_name}' with ID: {project_id}")

                # Check for existing dataset
                datasets = list(project.listChildren())
                dataset = None
                for ds in datasets:
                    if ds.getName() == dataset_name:
                        dataset = ds
                        break

                if dataset:
                    dataset_id = dataset.getId()
                    print(
                        f"Using existing dataset '{dataset_name}' with ID: {dataset_id}"
                    )
                else:
                    # Create new dataset in existing project
                    dataset = DatasetI()
                    dataset.setName(rtypes.rstring(dataset_name))
                    dataset = conn.getUpdateService().saveAndReturnObject(dataset)
                    dataset_id = dataset.getId().getValue()

                    # Link to project
                    link = ProjectDatasetLinkI()
                    link.setParent(ProjectI(project_id, False))
                    link.setChild(DatasetI(dataset_id, False))
                    conn.getUpdateService().saveAndReturnObject(link)
                    print(f"Created new dataset '{dataset_name}' with ID: {dataset_id}")
            else:
                # Create new project and dataset
                project_id, dataset_id = create_project_and_dataset(
                    conn, project_name, dataset_name
                )

        # Upload the file using ManagedRepository
        success = upload_to_managed_repository(conn, file_path, dataset_id)

        if success:
            print(f"\nSuccessfully initiated import of: {file_path}")
            print("Note: The server is now processing the file with Bio-Formats.")
            print("Check OMERO.web or OMERO.insight to see the imported image.")

        return success

    finally:
        conn.close()


def main():
    """Main function to upload bio image files to OMERO."""
    parser = argparse.ArgumentParser(
        description="Upload bio-image files to OMERO server"
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="testdata/xyc_tiles.czi",
        help="Path to the bio-image file to upload",
    )
    parser.add_argument(
        "--host", default="localhost", help="OMERO server hostname (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=4064, help="OMERO server port (default: 4064)"
    )
    parser.add_argument(
        "--username", "-u", default="root", help="OMERO username (default: root)"
    )
    parser.add_argument(
        "--password", "-w", default="omero", help="OMERO password (default: omero)"
    )
    parser.add_argument("--dataset", "-d", type=int, help="Dataset ID to import into")
    parser.add_argument(
        "--project-name",
        default="Test Project",
        help="Name for new project (if no dataset ID provided)",
    )
    parser.add_argument(
        "--dataset-name",
        default="Test Dataset",
        help="Name for new dataset (if no dataset ID provided)",
    )

    args = parser.parse_args()

    success = import_bioimage(
        args.file,
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        dataset_id=args.dataset,
        project_name=args.project_name,
        dataset_name=args.dataset_name,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
