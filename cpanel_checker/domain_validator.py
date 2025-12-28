"""Domain validation utilities."""

import socket
import logging


class DomainValidator:
    """Validates domains against IP whitelist."""
    
    def __init__(self, ip_whitelist=None):
        """Initialize domain validator.
        
        Args:
            ip_whitelist: List of whitelisted IP addresses
        """
        self.ip_whitelist = ip_whitelist or []
        self.log = logging.getLogger(__name__)
    
    def check_in_whitelist(self, domain):
        """Check if domain resolves to a whitelisted IP.
        
        Args:
            domain: Domain name to check
        
        Returns:
            tuple: (is_valid, error_code) where error_code is None if valid
        """
        try:
            ip = socket.gethostbyname(domain)
        except socket.gaierror:
            return False, "unresolvable"
        
        if ip in self.ip_whitelist:
            return True, None
        else:
            return False, "not_whitelisted"
