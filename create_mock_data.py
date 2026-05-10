"""Create mock database and output files for testing the web interface."""

import sqlite3
import struct
import zlib
from pathlib import Path

DB_PATH = "site_checker.db"
OUTPUT_DIR = Path(".")

# Two runs on today's date and one yesterday
RUNS = {
    "prev_yesterday": "2026050901",
    "yesterday":      "2026050901",
    "prev_today":     "2026051001",
    "today":          "2026051002",
}

HOSTS = ["cpanel1.example.com", "cpanel2.example.com"]

SITES = [
    # (host, user, domain)
    ("cpanel1.example.com", "alice",   "alice-photography.com"),
    ("cpanel1.example.com", "bobcorp", "bobcorp.net"),
    ("cpanel1.example.com", "charlie", "charlie-dev.io"),
    ("cpanel2.example.com", "diana",   "diana-boutique.com"),
    ("cpanel2.example.com", "eveshop", "eveshop.co.uk"),
]


def make_png(width: int = 200, height: int = 150, color: tuple = (100, 149, 237)) -> bytes:
    """Generate a minimal valid PNG with a solid colour."""
    def png_chunk(tag: bytes, data: bytes) -> bytes:
        c = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", c)

    raw_rows = b""
    r, g, b = color
    row = bytes([0] + [r, g, b] * width)
    for _ in range(height):
        raw_rows += row

    compressed = zlib.compress(raw_rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", compressed)
        + png_chunk(b"IEND", b"")
    )


def create_text_file(path: Path, domain: str, run: str, content_variant: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"Site: {domain}\n"
        f"Run:  {run}\n\n"
        f"Welcome to {domain}\n"
        f"This is the home page content captured during run {run}.\n"
        + content_variant
    )


def create_png_file(path: Path, color: tuple):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(make_png(color=color))


def setup_files():
    for host, user, domain in SITES:
        for run_key, run_id in RUNS.items():
            run_dir = OUTPUT_DIR / run_id / host
            txt = run_dir / f"{user}-{domain}.txt"
            if not txt.exists():
                variant = f"\nExtra content added in {run_id}.\n" if "today" in run_key else ""
                create_text_file(txt, domain, run_id, variant)

            png = run_dir / f"{user}-{domain}.png"
            if not png.exists():
                color = (100, 149, 237) if "prev" in run_key else (70, 130, 180)
                create_png_file(png, color)

        # Diff PNG only for current run
        for run_id in [RUNS["today"]]:
            diff = OUTPUT_DIR / run_id / host / f"{user}-{domain}-diff.png"
            if not diff.exists():
                create_png_file(diff, (255, 80, 80))


def setup_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS check_results (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp               TEXT NOT NULL,
            host                    TEXT NOT NULL,
            user                    TEXT NOT NULL,
            domain                  TEXT NOT NULL,
            code                    TEXT,
            location                TEXT,
            digest                  TEXT,
            txt_status              TEXT,
            txt_previous_run        TEXT,
            screenshot_hash_distance INTEGER,
            screenshot_status       TEXT,
            screenshot_previous_run TEXT
        )
    """)
    for idx in ["idx_domain", "idx_timestamp", "idx_host_user"]:
        conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON check_results("
                     + ("domain" if "domain" in idx else "timestamp" if "time" in idx else "host, user")
                     + ")")

    rows = []
    # Yesterday: a few text changes
    for host, user, domain in SITES[:3]:
        rows.append((
            "2026-05-09T14:22:10", host, user, domain,
            200, None, f"abc{hash(domain) & 0xFFFF:04x}",
            "different", RUNS["prev_yesterday"],
            5, "different", RUNS["prev_yesterday"],
        ))
    # Today: more changes across both servers
    for i, (host, user, domain) in enumerate(SITES):
        txt_st  = "different" if i % 2 == 0 else "same"
        shot_st = "different" if i % 2 == 1 else "different"
        rows.append((
            f"2026-05-10T09:0{i}:30", host, user, domain,
            200, None, f"def{hash(domain) & 0xFFFF:04x}",
            txt_st,  RUNS["prev_today"],
            8 + i,   shot_st, RUNS["prev_today"],
        ))
    # Some unchanged records (should NOT appear in UI)
    for host, user, domain in SITES:
        rows.append((
            "2026-05-10T09:30:00", host, user, domain,
            200, None, "unchanged",
            "same", RUNS["prev_today"],
            0, "same", RUNS["prev_today"],
        ))

    conn.executemany("""
        INSERT INTO check_results
            (timestamp, host, user, domain, code, location, digest,
             txt_status, txt_previous_run,
             screenshot_hash_distance, screenshot_status, screenshot_previous_run)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    conn.close()
    print(f"Created {DB_PATH} with {len(rows)} records.")


if __name__ == "__main__":
    setup_files()
    setup_db()
    print("Mock data ready.")
