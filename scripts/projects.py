from omero.gateway import BlitzGateway

with BlitzGateway("root", "omero", host="localhost", port=4064, secure=True) as conn:
    for p in conn.getObjects('Project'):
        print(p.name)
