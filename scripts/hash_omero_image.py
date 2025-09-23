from omero.gateway import BlitzGateway
import hashlib
import struct
import iscc_sum as isum

conn = BlitzGateway("root", "omero", host="omero.iscc.id", port=4064)
conn.connect()

image = conn.getObject("Image", 51)
pixels = image.getPrimaryPixels()
pixels_id = pixels.getId()

# Canonical order: T-major, then C, then Z (choose and stick to it!)
size_x, size_y = image.getSizeX(), image.getSizeY()
size_z, size_c, size_t = image.getSizeZ(), image.getSizeC(), image.getSizeT()
ptype = pixels.getPixelsType().getValue()  # e.g. "uint16", "float"

rps = conn.createRawPixelsStore()
try:
    rps.setPixelsId(pixels_id, False)

    # Build a header with shape + pixel type to bind the content/context
    sha = hashlib.sha256()
    s = isum.IsccSumProcessor()
    header = f"{size_x},{size_y},{size_z},{size_c},{size_t},{ptype}".encode("utf-8")
    print("Header:", header)
    sha.update(header)
    s.update(header)

    # Stream plane bytes deterministically
    for t in range(size_t):
        for c in range(size_c):
            for z in range(size_z):
                plane_bytes = rps.getPlane(z, c, t)  # ::Ice::ByteSeq (bytes)
                sha.update(plane_bytes)
                s.update(plane_bytes)

    print(
        "Image",
        image.getId(),
        "SHA256(normalized pixels) =",
        sha.hexdigest(),
        s.result(wide=True, add_units=True),
    )
finally:
    rps.close()
    conn.close()
