from omero.gateway import BlitzGateway, _ImageWrapper, MapAnnotationWrapper
import os
import pathlib

HERE = pathlib.Path(__file__).parent.absolute()


def download_original_file(conn, image_id, target_directory):
    image = conn.getObject("Image", image_id)
    if image is None:
        print(f"Image {image_id} not found.")
        return

    original_files = list(image.getImportedImageFiles())
    for original_file in original_files:
        file_id = original_file.getId()
        file_name = original_file.getName()
        file_size = original_file.getSize()

        print(
            f"Downloading file '{file_name}' (ID: {file_id}, size: {file_size} bytes)"
        )

        # Prepare local file path
        local_file_path = os.path.join(target_directory, file_name)

        # Download original file from OMERO
        with open(local_file_path, "wb") as local_file:
            for chunk in original_file.getFileInChunks():
                local_file.write(chunk)

        print(f"File '{file_name}' downloaded to {local_file_path}")


def list_images(conn):
    images = conn.getObjects("Image")
    for image in images:
        print(image.getAcquisitionDate())
        try:
            print(image.getInstrument().getMicroscope().getMicroscopeType())
        except Exception:
            pass
        # image.
        # annotations = list(image.listAnnotations())
        # return annotations
        # identifiers = [ann for ann in annotations if
        #                ann.getNs() == "custom.identifier.namespace"]
        #
        # if not identifiers:
        #     print(f"Processing image ID: {image.id}")


def process_new_images(conn):
    new_images = conn.getObjects(
        "Image", opts={"order_by": "creationEvent", "limit": 10}
    )
    for image in new_images:
        identifier = "ISCC:GABW5LUBVP23N3DOD7PPINHT5JKBI"

        # Add identifier to image metadata (key-value pairs)
        map_ann = MapAnnotationWrapper(conn)
        map_ann.setValue([["ISCC", identifier]])
        map_ann.save()
        image.linkAnnotation(map_ann)
        print(f"Identifier {identifier} added to image ID {image.id}")


if __name__ == "__main__":
    conn = BlitzGateway("root", "omero", host="localhost", port=4064, secure=True)
    if conn.connect():
        # print(list_images(conn))
        # download_original_file(conn, image_id=1, target_directory=HERE)
        process_new_images(conn)
        conn.close()
