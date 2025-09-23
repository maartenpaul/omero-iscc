# OMERO ISCC Service

An automated background service that generates ISCCs for images imported into OMERO.

## Overview

This service monitors OMERO for newly imported images and automatically:
- Generates ISCC-SUM fingerprints from the raw bioimaging data
- Stores ISCCs as MapAnnotations on the images

## Dependencies and related projects:

Omero Server: https://github.com/ome/openmicroscopy / https://deepwiki.com/ome/openmicroscopy
Omero Python Client: https://github.com/ome/omero-py / https://deepwiki.com/ome/omero-py
Omero Example Scripts: https://github.com/ome/omero-scripts / https://deepwiki.com/ome/omero-scripts
Omero Docker Example: https://github.com/ome/docker-example-omero / https://deepwiki.com/ome/docker-example-omero
ISCC-CORE - Core algorithms reference implementations: https://github.com/iscc/iscc-core / https://deepwiki.com/iscc/iscc-core
ISCC-SUM - Data-Code and Instance-Code implementation: https://github.com/iscc/iscc-sum / https://deepwiki.com/iscc/iscc-sum
