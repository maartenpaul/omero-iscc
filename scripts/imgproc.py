from omero.gateway import BlitzGateway
import pathlib


HERE = pathlib.Path(__file__).parent.absolute()
PROJECT_ROOT = HERE.parent.absolute()


def omero_render_images(host, username, password, image_id, target_dir=PROJECT_ROOT):
    conn = BlitzGateway(username, password, host=host, port=4064, secure=True)
    if not conn.connect():
        raise Exception("Failed to connect to OMERO server.")
    try:
        image = conn.getObject("Image", image_id)
        if image is None:
            raise Exception(f"Image {image_id} not found.")

        # Retrieve OMERO's rendered RGB image (exactly as web client)
        size_z = image.getSizeZ()
        size_t = image.getSizeT()
        for t in range(size_t):
            for z in range(size_z):
                # Get rendered RGB plane (channels merged and contrast adjusted)
                rendered_plane = image.renderImage(z, t)
                rendered_plane.save(target_dir / f"image-{z}-{t}.png")
    finally:
        conn.close()


# Example usage:
if __name__ == "__main__":
    host = "localhost"
    username = "root"
    password = "omero"
    image_id = 1  # replace with your image ID
    omero_render_images(host, username, password, image_id)
