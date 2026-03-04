# -*- coding: utf-8 -*-
"""
Clear all Chroma collections in the project's vectorstore folder.

Usage:
    DEBUG=false .venv/bin/python lib/clear_vectorstore.py
    DEBUG=false .venv/bin/python lib/clear_vectorstore.py --folder /path/to/vectorstore
"""

import argparse

import knova_utils as utils


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear project vectorstore collections.")
    parser.add_argument(
        "--folder",
        default=str(utils.VECTORSTORE_FOLDER),
        help="Vectorstore folder path (default: project vectorstore folder).",
    )
    args = parser.parse_args()

    print(f"<clear_vectorstore.py> Clearing vectorstore at: {args.folder}")
    utils.clear_vectorstore(args.folder)
    print("<clear_vectorstore.py> Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
