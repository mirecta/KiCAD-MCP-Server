"""
Bulk SQLite loader for JLCPCB-style parts databases.

Downloads a SQLite database (e.g. yaqwsx/jlcparts GitHub release artifact),
introspects its schema, and imports rows into JLCPCBPartsManager via the
existing import_jlcsearch_parts path (which uses .get() with flexible field
names, so it tolerates schema drift in upstream projects).
"""

from __future__ import annotations

import io
import logging
import os
import sqlite3
import tempfile
import zipfile
from typing import Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_YAQWSX_RELEASE_API = (
    "https://api.github.com/repos/yaqwsx/jlcparts/releases/latest"
)


class SqliteBulkLoader:
    """Fetch a remote SQLite (or zipped SQLite) and import rows into our DB."""

    def __init__(self, parts_manager) -> None:
        self.parts_manager = parts_manager

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _resolve_yaqwsx_asset_url(self) -> str:
        resp = requests.get(DEFAULT_YAQWSX_RELEASE_API, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for asset in data.get("assets", []):
            name = (asset.get("name") or "").lower()
            if name.endswith(".zip") or name.endswith(".sqlite3") or name.endswith(".db"):
                return asset["browser_download_url"]
        raise RuntimeError(
            f"No SQLite-like asset found in yaqwsx release '{data.get('tag_name')}'"
        )

    def _stream_download(self, url: str, dest_path: str,
                         progress: Optional[Callable[[int, int], None]] = None) -> None:
        with requests.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(dest_path, "wb") as fp:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if not chunk:
                        continue
                    fp.write(chunk)
                    downloaded += len(chunk)
                    if progress:
                        progress(downloaded, total)

    def _maybe_unzip(self, path: str, work_dir: str) -> str:
        if not zipfile.is_zipfile(path):
            return path
        with zipfile.ZipFile(path) as zf:
            members = [m for m in zf.namelist()
                       if m.lower().endswith((".sqlite3", ".sqlite", ".db"))]
            if not members:
                raise RuntimeError(
                    f"Zip {path} contains no .sqlite3/.sqlite/.db file: {zf.namelist()}"
                )
            extracted = zf.extract(members[0], work_dir)
            return extracted

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    @staticmethod
    def _list_tables(conn: sqlite3.Connection) -> List[str]:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return [r[0] for r in cur.fetchall()]

    @staticmethod
    def _row_count(conn: sqlite3.Connection, table: str) -> int:
        cur = conn.execute(f"SELECT COUNT(*) FROM \"{table}\"")
        return int(cur.fetchone()[0])

    def _pick_parts_table(self, conn: sqlite3.Connection,
                          override: Optional[str]) -> str:
        tables = self._list_tables(conn)
        if override:
            if override not in tables:
                raise RuntimeError(
                    f"Requested table '{override}' not in DB. Tables: {tables}"
                )
            return override
        # Prefer the largest table that looks like a parts table
        candidates = sorted(
            ((self._row_count(conn, t), t) for t in tables),
            reverse=True,
        )
        if not candidates:
            raise RuntimeError("Downloaded SQLite has no user tables")
        return candidates[0][1]

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def download_and_import(
        self,
        url: Optional[str] = None,
        table: Optional[str] = None,
        keep_file_at: Optional[str] = None,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> Dict:
        """
        Args:
            url: Direct URL to a .sqlite3 / .sqlite / .db file or a .zip
                 containing one. If omitted, resolves the latest yaqwsx/jlcparts
                 release asset.
            table: Override the parts table name. If omitted, the loader uses
                 the largest user table in the DB.
            keep_file_at: If provided, save the downloaded DB at this path
                 instead of a temp file.
            progress: Optional callback(downloaded_bytes, total_bytes).

        Returns:
            dict with success/imported_rows/table/path
        """
        resolved_url = url or self._resolve_yaqwsx_asset_url()
        logger.info(f"Downloading SQLite database from {resolved_url}")

        with tempfile.TemporaryDirectory() as work_dir:
            archive_path = os.path.join(work_dir, "asset.bin")
            self._stream_download(resolved_url, archive_path, progress=progress)
            db_path = self._maybe_unzip(archive_path, work_dir)

            if keep_file_at:
                os.makedirs(os.path.dirname(keep_file_at) or ".", exist_ok=True)
                # Atomic-ish move out of temp dir
                with open(db_path, "rb") as src, open(keep_file_at, "wb") as dst:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        dst.write(chunk)
                db_path = keep_file_at

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                parts_table = self._pick_parts_table(conn, table)
                logger.info(f"Importing from table '{parts_table}' in {db_path}")
                rows = [dict(r) for r in conn.execute(
                    f"SELECT * FROM \"{parts_table}\""
                )]
            finally:
                conn.close()

        if not rows:
            return {
                "success": False,
                "error": f"Table '{parts_table}' is empty",
                "table": parts_table,
            }

        # Re-use the existing flexible importer; it pulls common field names
        # with .get() so it tolerates whatever upstream schema this DB uses.
        self.parts_manager.import_jlcsearch_parts(rows)

        return {
            "success": True,
            "imported_rows": len(rows),
            "table": parts_table,
            "path": db_path if keep_file_at else None,
            "stats": self.parts_manager.get_database_stats(),
        }
