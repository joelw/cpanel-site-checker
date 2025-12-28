"""Web page fetching utilities."""

import requests
import socket
import logging
from urllib.parse import urljoin


class WebFetcher:
    """Fetches web pages with redirect handling."""
    
    def __init__(self, connect_timeout=30, read_timeout=30):
        """Initialize web fetcher.
        
        Args:
            connect_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
        """
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.log = logging.getLogger(__name__)
    
    def fetch_url(self, url, limit=5):
        """Fetch URL with manual redirect handling.
        
        Args:
            url: URL to fetch
            limit: Maximum number of redirects to follow
        
        Returns:
            tuple: (final_url, response) where response is None if error occurred
        """
        if limit == 0:
            return url, 0
        
        try:
            response = requests.get(
                url,
                allow_redirects=False,
                timeout=(self.connect_timeout, self.read_timeout)
            )
            
            # Handle redirects manually
            if response.status_code in [301, 302, 303, 307, 308]:
                location = response.headers.get('location')
                if location:
                    # Handle relative redirects
                    location = urljoin(url, location)
                    return self.fetch_url(location, limit - 1)
            
            return url, response
        except socket.error:
            # Return None response with 521 status to indicate server down
            class MockResponse:
                status_code = 521
            return url, MockResponse()
        except Exception as e:
            # Return None response with error message as status
            class MockResponse:
                status_code = str(e)
            return url, MockResponse()
