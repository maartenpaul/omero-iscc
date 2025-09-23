# OMERO ISCC Service

An automated background service that generates ISCCs for images imported into OMERO.

## Overview

This service monitors OMERO for newly imported images and automatically:
- Generates ISCC-SUM fingerprints from the raw bioimaging data
- Stores ISCCs as MapAnnotations on the images

## Quick Start

### Running All Services (Default)

The simplest way to run all services:

```bash
# Start all services (OMERO + ISCC)
docker compose up -d

# Stop all services
docker compose down
```

### Running Services Separately

You can also run the services independently:

```bash
# Start only OMERO services
docker compose -f compose.omero.yaml up -d

# Start only ISCC service (requires OMERO network to exist)
docker compose -f compose.omero.yaml up -d  # First ensure OMERO is running
docker compose -f compose.iscc.yaml up -d   # Then start ISCC

# Stop services individually
docker compose -f compose.omero.yaml down
docker compose -f compose.iscc.yaml down
```

### Service URLs

- OMERO API/Insight: http://localhost:4064
- OMERO Web: http://localhost:4080
- Default credentials: username=root, password=omero

## Dependencies and related development resources:

- OMERO Server: [OMERO](https://github.com/ome/openmicroscopy) (See: [Deepwiki](https://deepwiki.com/ome/openmicroscopy))
- ISCC-SUM - Data-Code and Instance-Code implementation: [ISCC-SUM](https://github.com/iscc/iscc-sum) (See: [Deepwiki](https://deepwiki.com/iscc/iscc-sum))
- OMERO Python Client: [omero-py](https://github.com/ome/omero-py) (See: [Deepwiki](https://deepwiki.com/ome/omero-py))
- OMERO Example Scripts: [omero-scripts](https://github.com/ome/omero-scripts) (See: [Deepwiki](https://deepwiki.com/ome/omero-scripts))
- OMERO Docker Example: [docker-example-omero](https://github.com/ome/docker-example-omero) (See: [Deepwiki](https://deepwiki.com/ome/docker-example-omero))
- ISCC-CORE - ISO 24138:2024 reference implementations: [ISCC-CORE](https://github.com/iscc/iscc-core) (See: [Deepwiki](https://deepwiki.com/iscc/iscc-core))

## Funding

This work was supported through the Open Science Clusters’ Action for Research and Society (OSCARS) European
project under grant agreement Nº101129751.

See:
[BIO-CODES](https://oscars-project.eu/projects/bio-codes-enhancing-ai-readiness-bioimaging-data-content-based-identifiers)
project (Enhancing AI-Readiness of Bioimaging Data with Content-Based Identifiers).

## License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.
