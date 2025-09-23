import iscc_sum as isum
import iscc_crypto as icr
from omero.gateway import BlitzGateway

conn = BlitzGateway("root", "omero", host="omero.iscc.id", port=4064, secure=True)
conn.connect()
conn.SERVICE_OPTS.setOmeroGroup("-1")
offset = 0
seen = {}
key = icr.key_from_platform()

for image in conn.getObjects("Image", respect_order=True, opts={"offset": offset}):
    print("Image:", image.getId(), image.getName())
    hasher = isum.IsccSumProcessor()
    orig_files = image.getImportedImageFiles()
    for orig_file in orig_files:
        file_id = orig_file.getId()
        file_hash = orig_file.getHash()
        print("  OriginalFile:", file_id, file_hash, orig_file.getName())
        result = seen.get(file_hash)
        if result:
            print("SKIP SEEN")
            break
        for chunk in orig_file.getFileInChunks():
            hasher.update(chunk)
        result = hasher.result(wide=True, add_units=True)
        seen[file_hash] = result
        print("    Result:", result)
    offset = image.getId()
