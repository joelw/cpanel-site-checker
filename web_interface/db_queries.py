"""Database query functions for web interface."""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class SiteCheckerDB:
    """Database query handler for site checker results."""

    def __init__(self, db_path: str = "../site_checker.db"):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
    def _get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_changes_by_date(self, date: str) -> List[Dict]:
        """Get all changes for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            
        Returns:
            List of dictionaries containing change records
        """
        conn = self._get_connection()
        try:
            # Query for records where txt_status or screenshot_status indicates a change
            # Date in timestamp column is ISO format, so we can use LIKE with date prefix
            query = """
                SELECT 
                    id,
                    timestamp,
                    host,
                    user,
                    domain,
                    code,
                    location,
                    digest,
                    txt_status,
                    txt_previous_run,
                    screenshot_hash_distance,
                    screenshot_status,
                    screenshot_previous_run
                FROM check_results
                WHERE DATE(timestamp) = ?
                AND (txt_status = 'different' OR screenshot_status = 'different')
                ORDER BY timestamp DESC
            """
            
            cursor = conn.execute(query, (date,))
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'host': row['host'],
                    'user': row['user'],
                    'domain': row['domain'],
                    'code': row['code'],
                    'location': row['location'],
                    'digest': row['digest'],
                    'txt_status': row['txt_status'],
                    'txt_previous_run': row['txt_previous_run'],
                    'screenshot_hash_distance': row['screenshot_hash_distance'],
                    'screenshot_status': row['screenshot_status'],
                    'screenshot_previous_run': row['screenshot_previous_run']
                })
            
            return results
        finally:
            conn.close()
    
    def get_available_dates(self) -> List[str]:
        """Get list of dates that have check results with changes.
        
        Returns:
            List of date strings in YYYY-MM-DD format
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT DISTINCT DATE(timestamp) as date
                FROM check_results
                WHERE txt_status = 'different' OR screenshot_status = 'different'
                ORDER BY date DESC
                LIMIT 100
            """
            
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            return [row['date'] for row in rows]
        finally:
            conn.close()
    
    def get_screenshot_paths(self, domain: str, user: str, current_run: str, 
                            previous_run: Optional[str], host: str,
                            output_dir: str = "..") -> Dict[str, Optional[str]]:
        """Get paths to current, previous, and diff screenshots.
        
        Args:
            domain: Domain name
            user: cPanel username
            current_run: Current run date serial (YYYYMMDDnn)
            previous_run: Previous run date serial (YYYYMMDDnn) or None
            host: Server hostname
            output_dir: Base output directory for screenshots
            
        Returns:
            Dictionary with 'current', 'previous', and 'diff' paths
        """
        result = {
            'current': None,
            'previous': None,
            'diff': None
        }
        
        # Build current screenshot path
        current_path = Path(output_dir) / current_run / host / f"{user}-{domain}.png"
        if current_path.exists():
            result['current'] = str(current_path)
        
        # Build diff screenshot path
        diff_path = Path(output_dir) / current_run / host / f"{user}-{domain}-diff.png"
        if diff_path.exists():
            result['diff'] = str(diff_path)
        
        # Build previous screenshot path if available
        if previous_run:
            previous_path = Path(output_dir) / previous_run / host / f"{user}-{domain}.png"
            if previous_path.exists():
                result['previous'] = str(previous_path)
        
        return result
    
    def get_text_file_paths(self, domain: str, user: str, current_run: str,
                           previous_run: Optional[str], host: str,
                           output_dir: str = "..") -> Dict[str, Optional[str]]:
        """Get paths to current and previous text files.
        
        Args:
            domain: Domain name
            user: cPanel username
            current_run: Current run date serial (YYYYMMDDnn)
            previous_run: Previous run date serial (YYYYMMDDnn) or None
            host: Server hostname
            output_dir: Base output directory for text files
            
        Returns:
            Dictionary with 'current' and 'previous' paths
        """
        result = {
            'current': None,
            'previous': None
        }
        
        # Build current text file path
        current_path = Path(output_dir) / current_run / host / f"{user}-{domain}.txt"
        if current_path.exists():
            result['current'] = str(current_path)
        
        # Build previous text file path if available
        if previous_run:
            previous_path = Path(output_dir) / previous_run / host / f"{user}-{domain}.txt"
            if previous_path.exists():
                result['previous'] = str(previous_path)
        
        return result
    
    def extract_run_from_timestamp(self, timestamp: str, output_dir: str = "..") -> Optional[str]:
        """Extract run date serial from timestamp by finding matching directory.
        
        Args:
            timestamp: ISO 8601 timestamp
            output_dir: Base output directory
            
        Returns:
            Run date serial (YYYYMMDDnn) or None
        """
        try:
            # Parse timestamp to get date
            dt = datetime.fromisoformat(timestamp)
            date_prefix = dt.strftime('%Y%m%d')
            
            # Find directories matching the date prefix
            output_path = Path(output_dir)
            if not output_path.exists():
                return None
            
            matching_dirs = [d.name for d in output_path.iterdir() 
                           if d.is_dir() and d.name.startswith(date_prefix)]
            
            if matching_dirs:
                # Sort and return the latest one for this date
                matching_dirs.sort(reverse=True)
                return matching_dirs[0]
            
            return None
        except Exception:
            return None
