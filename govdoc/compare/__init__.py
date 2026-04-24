"""DOCX comparison package."""

from govdoc.compare.service import (
    CompareDownload,
    create_compare_bundle,
    create_compare_bundle_from_bytes,
    get_compare_download,
)

__all__ = [
    "CompareDownload",
    "create_compare_bundle",
    "create_compare_bundle_from_bytes",
    "get_compare_download",
]
