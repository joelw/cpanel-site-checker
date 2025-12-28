#!/usr/bin/env python3
"""cPanel Site Checker - Main entry point."""

import os
import sys
import yaml
import urllib3

from cpanel_checker.site_checker import SiteChecker


def main():
    """Main entry point for the site checker."""
    configfile = 'servers.yml'

    if not os.path.exists(configfile):
        print(f"Error: {configfile} not found. Please create it from servers.yml.sample")
        sys.exit(1)

    with open(configfile, 'r') as f:
        config = yaml.safe_load(f)

    # Disable SSL warnings for self-signed certificates
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    checker = SiteChecker(config.get('config', {}))

    servers = config.get('servers', [])
    for server in servers:
        checker.check_accounts(server['host'], server['hash'], server.get('ips', []))


if __name__ == '__main__':
    main()
