"""Main site checker orchestration."""

import os
import sys
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .whm_api import WhmApiClient
from .domain_validator import DomainValidator
from .web_fetcher import WebFetcher
from .screenshot import ScreenshotManager


class SiteChecker:
    """Main site checker that orchestrates all components."""
    
    def __init__(self, config=None):
        """Initialize site checker.
        
        Args:
            config: Configuration dictionary
        """
        if config is None:
            config = {}
        
        self.output_dir = config.get('output_dir', '.')
        logfile = config.get('logfile')
        
        # Set up logging
        log_format = '%(asctime)s %(message)s'
        if logfile:
            logging.basicConfig(
                filename=logfile,
                level=logging.INFO,
                format=log_format,
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            logging.basicConfig(
                level=logging.INFO,
                format=log_format,
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        self.log = logging.getLogger(__name__)
        self.directory_format = config.get('directory_format', '%Y%m%d')
        self.lastrun_file = config.get('lastrun_file', 'lastrun.txt')
        
        # Set up Selenium with Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # Initialize components
        self.web_fetcher = WebFetcher(connect_timeout=30, read_timeout=30)
        self.screenshot_manager = ScreenshotManager(self.driver, self.output_dir)
    
    def __del__(self):
        """Clean up resources."""
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass
    
    def check_accounts(self, host, hash_key, date=None):
        """Check all accounts on a WHM server.
        
        Args:
            host: WHM server hostname
            hash_key: WHM API token/hash key
            date: Date string for directory organization (defaults to today)
        """
        if date is None:
            date = datetime.now().strftime(self.directory_format)
        
        # Initialize WHM API client
        whm_client = WhmApiClient(host, hash_key, read_timeout=30)
        
        # Set up output directory
        directory = os.path.join(self.output_dir, date, host)
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Get server IP addresses for whitelist
        try:
            ip_whitelist = whm_client.list_ips()
        except Exception as e:
            self.log.error(f"server.list_ips: {e}")
            sys.exit(1)
        
        # Initialize domain validator
        domain_validator = DomainValidator(ip_whitelist)
        
        # Get list of accounts
        try:
            accounts = whm_client.list_accounts()
        except Exception as e:
            self.log.error(f"Failed to list accounts: {e}")
            sys.exit(1)
        
        # Process each account
        for acct in accounts:
            if acct.get('suspended'):
                continue
            
            username = acct['user']
            
            # Get addon domains for this account
            domlist = whm_client.list_addon_domains(username)
            
            # Add the main domain to the list
            all_domains = [acct] + domlist
            
            # Validate domains against IP whitelist
            domains = []
            for account_domain in all_domains:
                domain = account_domain.get('domain')
                if not domain:
                    continue
                
                result, message = domain_validator.check_in_whitelist(domain)
                if result:
                    domains.append(domain)
                else:
                    self.log.warning(f"host={host} user={username} domain={domain} code={message}")
            
            # Fetch each domain
            for dom in domains:
                result = self._fetch_page(username, dom, directory)
                log_msg = f"host={host} user={username} domain={dom}"
                if 'code' in result:
                    log_msg += f" code={result['code']}"
                if 'location' in result:
                    log_msg += f" location={result['location']}"
                if 'digest' in result:
                    log_msg += f" digest={result['digest']}"
                if 'screenshot_diff' in result:
                    log_msg += f" screenshot_diff={result['screenshot_diff']}"
                self.log.info(log_msg)
        
        # Write to lastrun file
        with open(self.lastrun_file, 'a') as f:
            f.write(directory + '\n')
    
    def _fetch_page(self, user, domain, directory):
        """Fetch a single page and take screenshot.
        
        Args:
            user: cPanel username
            domain: Domain name
            directory: Output directory
        
        Returns:
            dict: Result dictionary with status information
        """
        url = f"http://{domain}"
        
        html_file = os.path.join(directory, f"{user}-{domain}.html")
        png_file = os.path.join(directory, f"{user}-{domain}.png")
        
        if os.path.exists(html_file) and os.path.exists(png_file):
            return {'code': 'skipped'}
        
        try:
            location, response = self.web_fetcher.fetch_url(url)
            
            if response == 0:
                return {'location': location, 'code': 'too_many_redirects'}
            
            # Save status and body
            with open(html_file, 'w') as f:
                f.write(location + '\n')
                if response is not None:
                    f.write(str(response.status_code) + '\n')
                    f.write(response.text + '\n')
            
            if response and response.status_code == 521:
                return {'code': '521'}
            
            # Take screenshot
            self.screenshot_manager.capture_screenshot(location, png_file)
            
            # Resize screenshot to 500px width thumbnail
            self.screenshot_manager.resize_screenshot(png_file, width=500)
            
            # Find previous screenshot and compare
            previous_screenshot = self.screenshot_manager.find_previous_screenshot(domain, directory)
            diff_percentage = None
            screenshot_kept = True
            
            if previous_screenshot:
                diff_percentage = self.screenshot_manager.compare_screenshots(png_file, previous_screenshot)
                
                if diff_percentage is not None:
                    # Use threshold to determine if screenshots are identical
                    if diff_percentage < self.screenshot_manager.SCREENSHOT_IDENTICAL_THRESHOLD:
                        # Screenshots are identical or nearly identical, delete the new one
                        os.remove(png_file)
                        screenshot_kept = False
                        self.log.info(f"domain={domain} screenshot_diff={diff_percentage:.2f}% action=deleted_identical")
                    else:
                        self.log.info(f"domain={domain} screenshot_diff={diff_percentage:.2f}%")
            
            digest = hashlib.sha256(response.content).hexdigest()
            result = {
                'location': location,
                'code': response.status_code,
                'digest': digest
            }
            
            # Only include screenshot_diff if screenshot was kept
            if diff_percentage is not None and screenshot_kept:
                result['screenshot_diff'] = f"{diff_percentage:.2f}%"
            
            return result
        except Exception as ex:
            return {'code': str(ex)}
