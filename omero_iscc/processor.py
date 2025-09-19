"""Process OMERO images to generate ISCC-SUM identifiers."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from iscc_sum import IsccSumProcessor
from omero.gateway import BlitzGateway, ImageWrapper, MapAnnotationWrapper

logger = logging.getLogger(__name__)


class IsccImageProcessor:
    """Process OMERO images to generate and store ISCC identifiers."""

    def __init__(
        self,
        conn: BlitzGateway,
        namespace: str = "org.iscc.omero.sum",
        chunk_size: int = 1024 * 1024  # 1MB chunks
    ):
        """Initialize the ISCC image processor.

        Args:
            conn: Active BlitzGateway connection
            namespace: Namespace for ISCC annotations
            chunk_size: Size of chunks for streaming file data
        """
        self.conn = conn
        self.namespace = namespace
        self.chunk_size = chunk_size

    def process_image(self, image: ImageWrapper) -> Optional[str]:
        """Process an image to generate ISCC-SUM.

        Args:
            image: Image to process

        Returns:
            ISCC code if successful, None otherwise
        """
        image_id = image.getId()
        image_name = image.getName()

        try:
            logger.info(f"Processing image: {image_name} (ID: {image_id})")

            # Get the original file(s)
            original_files = list(image.getImportedImageFiles())
            if not original_files:
                logger.warning(f"No original files found for image {image_id}")
                return None

            # Process the first/main original file
            orig_file = original_files[0]
            file_size = orig_file.getSize()

            logger.debug(f"Processing original file: {orig_file.getName()} ({file_size} bytes)")

            # Generate ISCC from original file data
            iscc_code = self._generate_iscc_for_file(orig_file)

            if iscc_code:
                # Store ISCC as annotation
                self._store_iscc_annotation(image, iscc_code, orig_file.getName())
                logger.info(f"Generated ISCC for image {image_id}: {iscc_code}")
                return iscc_code

        except Exception as e:
            logger.error(f"Error processing image {image_id}: {e}", exc_info=True)

        return None

    def _generate_iscc_for_file(self, original_file) -> Optional[str]:
        """Generate ISCC-SUM for an original file.

        Args:
            original_file: OriginalFile object from OMERO

        Returns:
            ISCC code string or None if failed
        """
        raw_store = None
        try:
            # Create raw file store to read file data
            raw_store = self.conn.c.sf.createRawFileStore()
            raw_store.setFileId(original_file.getId())

            # Initialize ISCC processor
            processor = IsccSumProcessor()

            # Stream file in chunks
            file_size = original_file.getSize()
            offset = 0
            bytes_processed = 0

            while offset < file_size:
                # Calculate chunk size (don't exceed file size)
                current_chunk_size = min(self.chunk_size, file_size - offset)

                # Read chunk from OMERO
                data = raw_store.read(offset, current_chunk_size)

                # Update ISCC processor
                processor.update(data)

                # Update progress
                offset += len(data)
                bytes_processed += len(data)

                # Log progress for large files
                if file_size > 10 * 1024 * 1024:  # > 10MB
                    progress = int((bytes_processed / file_size) * 100)
                    if progress % 20 == 0:
                        logger.debug(f"Processing progress: {progress}%")

            # Get final ISCC result
            result = processor.result(wide=True, add_units=False)
            return result.iscc

        except Exception as e:
            logger.error(f"Error generating ISCC: {e}", exc_info=True)
            return None

        finally:
            if raw_store:
                try:
                    raw_store.close()
                except Exception:
                    pass

    def _store_iscc_annotation(
        self,
        image: ImageWrapper,
        iscc_code: str,
        file_name: str
    ):
        """Store ISCC code as MapAnnotation on image.

        Args:
            image: Image to annotate
            iscc_code: ISCC identifier
            file_name: Name of processed file
        """
        try:
            # Create map annotation with ISCC metadata
            map_ann = MapAnnotationWrapper(self.conn)
            map_ann.setNs(self.namespace)

            # Store ISCC and metadata
            annotation_data = [
                ["iscc:sum", iscc_code],
                ["iscc:version", "1.0"],
                ["iscc:source_file", file_name],
                ["iscc:timestamp", datetime.now().isoformat()],
                ["iscc:processor", "omero-iscc-service"]
            ]

            map_ann.setValue(annotation_data)
            map_ann.save()

            # Link annotation to image
            image.linkAnnotation(map_ann)

            logger.debug(f"Stored ISCC annotation for image {image.getId()}")

        except Exception as e:
            logger.error(f"Error storing ISCC annotation: {e}", exc_info=True)
            raise

    def get_iscc_for_image(self, image: ImageWrapper) -> Optional[Dict[str, Any]]:
        """Get existing ISCC annotation for an image.

        Args:
            image: Image to check

        Returns:
            Dictionary with ISCC data or None if not found
        """
        try:
            for ann in image.listAnnotations():
                if ann.getNs() == self.namespace:
                    if hasattr(ann, 'getValue'):
                        values = ann.getValue()
                        # Convert to dictionary
                        result = {}
                        for key, value in values:
                            if key.startswith('iscc:'):
                                result[key] = value
                        if result:
                            return result
        except Exception as e:
            logger.error(f"Error getting ISCC annotation: {e}")

        return None