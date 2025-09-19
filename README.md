# OMERO ISCC Service

An automated background service that generates ISCC-SUM identifiers for all images imported into OMERO.

## Overview

This service monitors OMERO for newly imported images and automatically:
1. Detects new image imports using timeline queries
2. Downloads original raw file data via OMERO's RawFileStore
3. Generates ISCC-SUM identifiers from the raw data
4. Stores identifiers as MapAnnotations on the images

## Architecture

The service uses a polling-based architecture with three main components:

- **Monitor** (`omero_iscc/monitor.py`): Polls OMERO for new images
- **Processor** (`omero_iscc/processor.py`): Generates ISCC-SUM from raw files
- **Service Manager** (`omero_iscc/service_manager.py`): Orchestrates the service

## Installation

### Prerequisites

- Python 3.12+
- OMERO server (running and accessible)
- Required Python packages (see pyproject.toml)

### Install from source

```bash
# Clone the repository
git clone https://github.com/bio-codes/omero-iscc.git
cd omero-iscc

# Install with pip
pip install -e .
```

## Configuration

The service can be configured via:

1. **Environment variables** (prefix with `OMERO_ISCC_`):
```bash
export OMERO_ISCC_HOST=localhost
export OMERO_ISCC_PORT=4064
export OMERO_ISCC_USERNAME=root
export OMERO_ISCC_PASSWORD=omero
export OMERO_ISCC_POLL_INTERVAL=60
```

2. **Configuration file** (JSON):
```json
{
  "host": "localhost",
  "port": 4064,
  "username": "root",
  "password": "omero",
  "poll_interval": 60,
  "batch_size": 100,
  "namespace": "org.iscc.omero.sum"
}
```

3. **Command-line arguments**:
```bash
python -m omero_iscc --host localhost --port 4064 --username root
```

## Usage

### Run as standalone service

```bash
# Run continuously
python -m omero_iscc

# Run with custom config
python -m omero_iscc --config /path/to/config.json

# Run once for testing
python -m omero_iscc --once
```

### Run with Docker

```bash
# Build the image
docker build -t omero-iscc .

# Run the service
docker run -d \
  --name omero-iscc \
  -e OMERO_ISCC_HOST=omero-server \
  -e OMERO_ISCC_USERNAME=root \
  -e OMERO_ISCC_PASSWORD=omero \
  omero-iscc
```

### Run with Docker Compose

```bash
# Start OMERO and ISCC service together
docker compose -f compose.yaml -f compose.service.yaml up -d
```

### Run as systemd service (Linux)

```bash
# Copy service file
sudo cp systemd/omero-iscc.service /etc/systemd/system/

# Edit configuration
sudo systemctl edit omero-iscc.service

# Enable and start
sudo systemctl enable omero-iscc
sudo systemctl start omero-iscc

# Check status
sudo systemctl status omero-iscc
```

## Testing

Run the test suite to verify the service:

```bash
# Test all components
python scripts/test_iscc_service.py

# Test specific component
python scripts/test_iscc_service.py --test connection
python scripts/test_iscc_service.py --test processing
python scripts/test_iscc_service.py --test service
python scripts/test_iscc_service.py --test list
```

## How It Works

1. **Monitoring**: The service polls OMERO's timeline API every 60 seconds (configurable) for new images

2. **Processing**: For each new image:
   - Retrieves original file references via `getImportedImageFiles()`
   - Opens RawFileStore connection to read file data
   - Streams data through ISCC-SUM processor in chunks
   - Generates unique ISCC identifier

3. **Storage**: ISCC identifiers are stored as MapAnnotations with:
   - Namespace: `org.iscc.omero.sum`
   - Key-value pairs including ISCC code, timestamp, and metadata

4. **Verification**: The service checks for existing ISCC annotations to avoid reprocessing

## ISCC Annotation Format

Annotations are stored with the following structure:

```python
{
    "iscc:sum": "ISCC:KAD2XGH4AUDGVPKQFHYMQX3EMHULA",
    "iscc:version": "1.0",
    "iscc:source_file": "example.tiff",
    "iscc:timestamp": "2024-01-01T12:00:00",
    "iscc:processor": "omero-iscc-service"
}
```

## Querying ISCC Annotations

To find images with ISCC codes in OMERO:

```python
from omero.gateway import BlitzGateway

conn = BlitzGateway(username, password, host=host, port=4064)
conn.connect()

# Find all annotations in ISCC namespace
namespace = "org.iscc.omero.sum"
anns = conn.getObjects("MapAnnotation", attributes={"ns": namespace})

for ann in anns:
    values = ann.getValue()
    for key, value in values:
        if key == "iscc:sum":
            print(f"ISCC: {value}")
            # Get linked images
            for link in ann.listParents():
                print(f"  Image: {link.getName()} (ID: {link.getId()})")
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `host` | localhost | OMERO server hostname |
| `port` | 4064 | OMERO server port |
| `username` | root | OMERO username |
| `password` | omero | OMERO password |
| `poll_interval` | 60 | Seconds between polls |
| `batch_size` | 100 | Max images per poll |
| `chunk_size` | 1048576 | File read chunk size (bytes) |
| `namespace` | org.iscc.omero.sum | Annotation namespace |
| `log_level` | info | Logging level |
| `webhook_url` | None | Optional webhook for notifications |

## Deployment Considerations

### Performance

- Processing is I/O bound (file streaming)
- Default chunk size of 1MB balances memory and performance
- Batch size prevents overwhelming the server

### Security

- Store credentials securely (use environment variables or secrets management)
- Run service with minimal privileges
- Consider network isolation between service and OMERO

### Reliability

- Service automatically reconnects on connection loss
- Failed images are logged and skipped (not retried indefinitely)
- Graceful shutdown on SIGTERM/SIGINT

### Monitoring

- Service logs to stdout/stderr by default
- Integrates with systemd journal on Linux
- Optional webhook notifications for processed images

## Troubleshooting

### Service won't connect
- Check OMERO server is running: `docker compose ps`
- Verify credentials: `omero login`
- Check network connectivity to OMERO port 4064

### Images not being processed
- Check service logs for errors
- Verify images don't already have ISCC annotations
- Ensure original files are available in ManagedRepository

### Performance issues
- Reduce `batch_size` if processing is slow
- Increase `poll_interval` to reduce server load
- Check OMERO server resources (CPU, memory, disk I/O)

## License

See LICENSE file in the repository.

## Support

For issues and questions:
- GitHub Issues: https://github.com/bio-codes/omero-iscc/issues
- OMERO Community: https://forum.image.sc/tag/omero

## Dependencies and related projects:

Omero Server: https://github.com/ome/openmicroscopy / https://deepwiki.com/ome/openmicroscopy
Omero Python Client: https://github.com/ome/omero-py / https://deepwiki.com/ome/omero-py

Omero Example Scripts: https://github.com/ome/omero-scripts / https://deepwiki.com/ome/omero-scripts
Omero Docker Example: https://github.com/ome/docker-example-omero / https://deepwiki.com/ome/docker-example-omero
ISCC-CORE - Core algorithms reference implementations: https://github.com/iscc/iscc-core / https://deepwiki.com/iscc/iscc-core
ISCC-SUN - Data-Code and Instance-Code implementation: https://github.com/iscc/iscc-sum / https://deepwiki.com/iscc/iscc-sum
