import io
import os
from iscc_sum import IsccSumProcessor


def create_iscc_sum(stream):
    """Create ISCC-SUM from a stream of binary data.

    Returns:
        IsccSumResult(
            iscc='ISCC:K4ALF4YZZRVC7EHOVHY4BKQH4CYQI5AEZYMUTWYSLAFPU2FNJ2E5PCQ',
            datahash='1e207404ce1949db12580afa68ad4e89d78aa358a5254c6aafd04c92f820bee121f1',
            filesize=10485760,
            units=Some([
                "ISCC:GAD3F4YZZRVC7EHOVHY4BKQH4CYQJ3WO342JIZOCNSDJ6WRCMUAY3CY",
                "ISCC:IADXIBGODFE5WESYBL5GRLKORHLYVI2YUUSUY2VP2BGJF6BAX3QSD4I"
                ]
            )
        )
    """
    processor = IsccSumProcessor()
    while chunk := stream.read(1024 * 1024):  # Read in 1MB chunks
        processor.update(chunk)
    return processor.result(wide=True, add_units=True)


def main():
    data = os.urandom(1024 * 1024 * 10)
    result = create_iscc_sum(io.BytesIO(data))
    print(result)


if __name__ == "__main__":
    main()
