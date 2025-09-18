from omero.gateway import BlitzGateway, MapAnnotationWrapper


# Function to set key-value pair metadata on an OMERO image
def set_image_metadata(host, username, password, image_id, kv_pairs):
    conn = BlitzGateway(username, password, host=host, port=4064, secure=True)
    if not conn.connect():
        raise Exception("Failed to connect to OMERO server.")

    try:
        # Retrieve the image by ID
        image = conn.getObject("Image", image_id)
        if image is None:
            raise Exception(f"Image with ID {image_id} not found.")

        # Create MapAnnotation (key-value pairs)
        map_ann = MapAnnotationWrapper(conn)
        map_ann.setValue(kv_pairs)
        map_ann.save()

        # Link annotation to the image
        image.linkAnnotation(map_ann)

        print(f"Successfully set metadata on image {image_id}.")

    finally:
        conn.close()


if __name__ == "__main__":
    host = 'localhost'
    username = 'root'
    password = 'omero'
    image_id = 3

    # Example key-value pairs
    kv_pairs = [
        ("ISCC", "ISCC:GABW5LUBVP23N3DOD7PPINHT5JKBI"),
    ]

    set_image_metadata(host, username, password, image_id, kv_pairs)
    print(f"Successfully set metadata on image {image_id}.")
