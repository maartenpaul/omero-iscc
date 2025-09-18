"""Check images in OMERO server."""

from omero.gateway import BlitzGateway

def check_images():
    """Check all images in OMERO."""
    conn = BlitzGateway('root', 'omero', host='localhost', port=4064, secure=True)

    if not conn.connect():
        print("Failed to connect")
        return

    try:
        # Check all projects and datasets
        print("\n=== Projects and Datasets ===")
        for project in conn.getObjects("Project"):
            print(f"Project: {project.getName()} (ID: {project.getId()})")
            for dataset in project.listChildren():
                print(f"  Dataset: {dataset.getName()} (ID: {dataset.getId()})")
                image_count = 0
                for image in dataset.listChildren():
                    image_count += 1
                    print(f"    Image: {image.getName()} (ID: {image.getId()})")
                if image_count == 0:
                    print(f"    (No images)")

        # Check all images (including orphaned ones)
        print("\n=== All Images ===")
        all_images = list(conn.getObjects("Image"))
        if all_images:
            for img in all_images:
                print(f"Image: {img.getName()} (ID: {img.getId()})")
                # Check parent dataset
                parent = img.getParent()
                if parent:
                    print(f"  Parent dataset: {parent.getName()}")
                else:
                    print(f"  Orphaned (no dataset)")
        else:
            print("No images found in OMERO")

        # Check filesets
        print("\n=== Filesets ===")
        filesets = list(conn.getObjects("Fileset"))
        for fs in filesets:
            print(f"Fileset ID: {fs.getId()}")
            for entry in fs.listFiles():
                print(f"  File: {entry.getName()}")

    finally:
        conn.close()

if __name__ == "__main__":
    check_images()