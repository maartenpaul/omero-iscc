from omero.gateway import BlitzGateway

with BlitzGateway("root", "omero", host="localhost", port=4064, secure=True) as conn:
    for p in conn.getObjects("Project"):
        print(f"Project: {p.name} (ID: {p.id})")
        for d in p.listChildren():
            print(f"  Dataset: {d.name} (ID: {d.id})")
            image_count = 0
            for i in d.listChildren():
                print(f"    Image: {i.name} (ID: {i.id})")
                image_count += 1
            if image_count == 0:
                print(f"    No images in dataset")
        print()
