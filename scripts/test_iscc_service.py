"""Test script for OMERO ISCC service."""

import sys
import time
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from omero.gateway import BlitzGateway
from omero_iscc.config import ServiceConfig
from omero_iscc.service_manager import IsccServiceManager
from omero_iscc.processor import IsccImageProcessor


def test_connection(config: ServiceConfig) -> bool:
    """Test connection to OMERO server.

    Args:
        config: Service configuration

    Returns:
        True if connection successful
    """
    print(f"Testing connection to {config.host}:{config.port}...")

    conn = BlitzGateway(
        username=config.username,
        passwd=config.password,
        host=config.host,
        port=config.port,
        secure=config.secure
    )

    if conn.connect():
        print("✓ Connection successful")
        user = conn.getUser()
        print(f"  Connected as: {user.getName()} (ID: {user.getId()})")
        conn.close()
        return True
    else:
        print("✗ Connection failed")
        return False


def test_image_processing(config: ServiceConfig) -> bool:
    """Test processing a single image.

    Args:
        config: Service configuration

    Returns:
        True if processing successful
    """
    print("\nTesting image processing...")

    conn = BlitzGateway(
        username=config.username,
        passwd=config.password,
        host=config.host,
        port=config.port,
        secure=config.secure
    )

    if not conn.connect():
        print("✗ Failed to connect")
        return False

    try:
        # Get an image to test
        images = []
        for img in conn.getObjects("Image"):
            images.append(img)
            if len(images) >= 1:
                break
        if not images:
            print("✗ No images found in OMERO")
            return False

        image = images[0]
        print(f"  Testing with image: {image.getName()} (ID: {image.getId()})")

        # Create processor
        processor = IsccImageProcessor(conn, namespace=config.namespace)

        # Check if already has ISCC
        existing = processor.get_iscc_for_image(image)
        if existing:
            print(f"  Image already has ISCC: {existing.get('iscc:sum')}")
            return True

        # Process the image
        print("  Generating ISCC-SUM...")
        iscc_code = processor.process_image(image)

        if iscc_code:
            print(f"✓ Successfully generated ISCC: {iscc_code}")

            # Verify it was stored
            stored = processor.get_iscc_for_image(image)
            if stored:
                print(f"✓ ISCC annotation verified: {stored.get('iscc:sum')}")
                return True
            else:
                print("✗ ISCC annotation not found after processing")
                return False
        else:
            print("✗ Failed to generate ISCC")
            return False

    except Exception as e:
        print(f"✗ Error during processing: {e}")
        return False

    finally:
        conn.close()


def test_service_cycle(config: ServiceConfig) -> bool:
    """Test a single service poll cycle.

    Args:
        config: Service configuration

    Returns:
        True if cycle successful
    """
    print("\nTesting service poll cycle...")

    service = IsccServiceManager(config)

    try:
        # Connect
        if not service.connect():
            print("✗ Service failed to connect")
            return False

        print("✓ Service connected")

        # Initialize
        service.initialize_components()
        print("✓ Components initialized")

        # Run one cycle
        print("  Running poll cycle...")
        count = service.run_once()
        print(f"✓ Poll complete: {count} new images found")

        # Get status
        status = service.status()
        print("\n  Service status:")
        print(f"    Connected: {status['connected']}")
        print(f"    Processed: {status['monitor']['processed_count']} images")

        return True

    except Exception as e:
        print(f"✗ Service error: {e}")
        return False

    finally:
        service.stop()


def test_recent_images(config: ServiceConfig) -> bool:
    """List recent images in OMERO.

    Args:
        config: Service configuration

    Returns:
        True if successful
    """
    print("\nListing recent images...")

    conn = BlitzGateway(
        username=config.username,
        passwd=config.password,
        host=config.host,
        port=config.port,
        secure=config.secure
    )

    if not conn.connect():
        print("✗ Failed to connect")
        return False

    try:
        # Get recent images using timeline
        images = list(conn.timelineListImages())[:10]  # Get up to 10 recent images

        if not images:
            print("  No images found")
            return True

        print(f"  Found {len(images)} recent images:")

        # Create processor to check for ISCCs
        processor = IsccImageProcessor(conn, namespace=config.namespace)

        for image in images:
            iscc_data = processor.get_iscc_for_image(image)
            if iscc_data:
                iscc_code = iscc_data.get('iscc:sum', 'N/A')
                status = "✓ Has ISCC"
            else:
                iscc_code = "Not processed"
                status = "  No ISCC"

            print(f"    {status} | ID: {image.getId():4d} | {image.getName()[:40]:40s} | {iscc_code}")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    finally:
        conn.close()


def main():
    """Run tests for OMERO ISCC service."""
    parser = argparse.ArgumentParser(description='Test OMERO ISCC Service')
    parser.add_argument('--host', default='localhost', help='OMERO server host')
    parser.add_argument('--port', type=int, default=4064, help='OMERO server port')
    parser.add_argument('--username', default='root', help='OMERO username')
    parser.add_argument('--password', default='omero', help='OMERO password')
    parser.add_argument('--test', choices=['all', 'connection', 'processing', 'service', 'list'],
                        default='all', help='Which test to run')

    args = parser.parse_args()

    # Create config
    config = ServiceConfig(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password
    )

    print("=" * 60)
    print("OMERO ISCC Service Test Suite")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Run tests based on selection
    if args.test in ['all', 'connection']:
        if test_connection(config):
            tests_passed += 1
        else:
            tests_failed += 1

    if args.test in ['all', 'list']:
        if test_recent_images(config):
            tests_passed += 1
        else:
            tests_failed += 1

    if args.test in ['all', 'processing']:
        if test_image_processing(config):
            tests_passed += 1
        else:
            tests_failed += 1

    if args.test in ['all', 'service']:
        if test_service_cycle(config):
            tests_passed += 1
        else:
            tests_failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Test Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)

    return 0 if tests_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())