"""Database logging for site checker results."""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path


class DatabaseLogger:
    """Manages SQLite database logging for site checker results."""

    def __init__(self, db_path='site_checker.db'):
        """Initialize database logger.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.log = logging.getLogger(__name__)
        self.conn = None
        self._init_database()

    def _init_database(self):
        """Initialize database connection and create tables if needed."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            
            # Create tables
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS check_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    host TEXT NOT NULL,
                    user TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    code TEXT,
                    location TEXT,
                    digest TEXT,
                    txt_status TEXT,
                    txt_previous_run TEXT,
                    screenshot_hash_distance INTEGER,
                    screenshot_status TEXT,
                    screenshot_previous_run TEXT
                )
            ''')
            
            # Create indexes for common queries
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_domain 
                ON check_results(domain)
            ''')
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON check_results(timestamp)
            ''')
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_host_user 
                ON check_results(host, user)
            ''')
            
            self.conn.commit()
            self.log.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            self.log.error(f"Failed to initialize database: {e}")
            raise

    def log_check_result(self, host, user, domain, result):
        """Log a site check result to the database.

        Args:
            host: WHM server hostname
            user: cPanel username
            domain: Domain name
            result: Dictionary containing check results with keys like:
                    code, location, digest, txt_status, txt_previous_run,
                    screenshot_hash_distance, screenshot_status, screenshot_previous_run
        """
        try:
            timestamp = datetime.now().isoformat()
            
            self.conn.execute('''
                INSERT INTO check_results (
                    timestamp, host, user, domain, code, location, digest,
                    txt_status, txt_previous_run, screenshot_hash_distance,
                    screenshot_status, screenshot_previous_run
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                host,
                user,
                domain,
                result.get('code'),
                result.get('location'),
                result.get('digest'),
                result.get('txt_status'),
                result.get('txt_previous_run'),
                result.get('screenshot_hash_distance'),
                result.get('screenshot_status'),
                result.get('screenshot_previous_run')
            ))
            
            self.conn.commit()
        except Exception as e:
            self.log.error(f"Failed to log check result for {domain}: {e}")

    def close(self):
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
                self.log.info("Database connection closed")
            except Exception as e:
                self.log.error(f"Error closing database: {e}")
