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

## Dependencies and related projects:

Omero Server: https://github.com/ome/openmicroscopy / https://deepwiki.com/ome/openmicroscopy
Omero Python Client: https://github.com/ome/omero-py / https://deepwiki.com/ome/omero-py
Omero Example Scripts: https://github.com/ome/omero-scripts / https://deepwiki.com/ome/omero-scripts
Omero Docker Example: https://github.com/ome/docker-example-omero / https://deepwiki.com/ome/docker-example-omero
ISCC-CORE - Core algorithms reference implementations: https://github.com/iscc/iscc-core / https://deepwiki.com/iscc/iscc-core
ISCC-SUM - Data-Code and Instance-Code implementation: https://github.com/iscc/iscc-sum / https://deepwiki.com/iscc/iscc-sum
