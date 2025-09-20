"""Test script to verify ISCC annotation format matches iscc_sum_processing output."""

import io
import os
from iscc_sum import IsccSumProcessor


def test_iscc_format():
    """Test that the ISCC-SUM processor returns the expected format."""
    # Create test data (10MB random data)
    data = os.urandom(1024 * 1024 * 10)

    # Process with ISCC-SUM
    processor = IsccSumProcessor()
    stream = io.BytesIO(data)
    while chunk := stream.read(1024 * 1024):
        processor.update(chunk)

    # Get result with units
    result = processor.result(wide=True, add_units=True)

    print("ISCC-SUM Processor Output:")
    print(f"  iscc: {result.iscc}")
    print(f"  datahash: {result.datahash}")
    print(f"  filesize: {result.filesize}")
    print(f"  units: {result.units}")

    # Expected annotation format
    print("\nExpected OMERO Annotation Format:")
    print(f"  iscc:sum -> {result.iscc}")
    if result.units and len(result.units) >= 2:
        print(f"  iscc:data -> {result.units[0]}")
        print(f"  iscc:inst -> {result.units[1]}")

    return result


if __name__ == "__main__":
    test_iscc_format()
