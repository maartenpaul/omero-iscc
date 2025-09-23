from datetime import datetime, timezone
import niquests
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
        note = {
            "iscc_code": result.iscc,
            "datahash": result.datahash,
            "nonce": icr.create_nonce(0),
            "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            "gateway": f"https://omero.iscc.id/webclient/?show=image-{image.getId()}",
            "units": list(result.units)[:-1],
        }
        signed_note = icr.sign_json(note, keypair=key)
        try:
            response = niquests.post("https://sb0.iscc.id/declaration", json=signed_note)
        except Exception as e:
            print("    Error:", e)
            continue

        print("    NiQuests:", response.json())
        print("    Result:", result)
    offset = image.getId()
