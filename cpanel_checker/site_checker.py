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

        # Set up Selenium with Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=chrome_options)

        # Initialize components
        self.screenshot_manager = ScreenshotManager(self.driver, self.output_dir)

    def _get_next_date_serial(self):
        """Generate next date directory with serial number (YYYYMMDDnn).

        Returns:
            str: Date string with serial number (e.g., '2025122801')

        Raises:
            RuntimeError: If serial number would exceed 99
        """
        today = datetime.now().strftime('%Y%m%d')

        # Find existing directories for today
        pattern = f"{today}*"
        existing_dirs = []

        if os.path.exists(self.output_dir):
            for entry in os.listdir(self.output_dir):
                if os.path.isdir(os.path.join(self.output_dir, entry)) and entry.startswith(today):
                    existing_dirs.append(entry)

        # Find highest serial number
        max_serial = 0
        for dirname in existing_dirs:
            if len(dirname) == 10:  # YYYYMMDDnn
                try:
                    serial = int(dirname[8:])
                    max_serial = max(max_serial, serial)
                except ValueError:
                    pass

        # Increment and check limit
        next_serial = max_serial + 1
        if next_serial > 99:
            raise RuntimeError(f"Cannot create more than 99 directories in one day (reached {next_serial})")

        return f"{today}{next_serial:02d}"

    def __del__(self):
        """Clean up resources."""
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass

    def check_accounts(self, host, hash_key, ip_allowlist=[], date=None):
        """Check all accounts on a WHM server.

        Args:
            host: WHM server hostname
            hash_key: WHM API token/hash key
            date: Date string for directory organization (defaults to today)
        """
        if date is None:
            date = self._get_next_date_serial()

        # Initialize WHM API client
        whm_client = WhmApiClient(host, hash_key, read_timeout=30)

        # Set up output directory
        directory = os.path.join(self.output_dir, date, host)
        Path(directory).mkdir(parents=True, exist_ok=True)

        # Initialize domain validator
        domain_validator = DomainValidator(ip_allowlist)

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

    def _fetch_page(self, user, domain, directory):
        """Fetch a single page and take screenshot.

        Args:
            user: cPanel username
            domain: Domain name
            directory: Output directory

        Returns:
            dict: Result dictionary with status information
        """
        url = f"https://{domain}"

        html_file = os.path.join(directory, f"{user}-{domain}.txt")
        png_file = os.path.join(directory, f"{user}-{domain}.png")

        if os.path.exists(html_file) and os.path.exists(png_file):
            return {'code': 'skipped'}

        try:
            # Take screenshot (this will load the page in Selenium with redirects)
            self.screenshot_manager.capture_screenshot(url, png_file)

            # Get final URL after any redirects
            location = self.driver.current_url

            # Get HTTP status code using JavaScript
            try:
                status_code = self.driver.execute_script("""
                    const entries = performance.getEntriesByType('navigation');
                    if (entries && entries.length > 0) {
                        return entries[0].responseStatus || 200;
                    }
                    return 200;
                """)
            except:
                status_code = 200  # Fallback if script fails

            # Get visible page text from Selenium after JavaScript has executed
            page_text = self.driver.find_element('tag name', 'body').text

            # Save location, status code, and visible text
            with open(html_file, 'w') as f:
                f.write(location + '\n')
                f.write(str(status_code) + '\n')
                f.write(page_text + '\n')

            # Resize screenshot to 500px width thumbnail
            self.screenshot_manager.resize_screenshot(png_file, width=500)

            # Find previous screenshot and compare
            previous_screenshot = self.screenshot_manager.find_previous_screenshot(domain, directory)
            diff_percentage = None
            screenshot_kept = True

            if previous_screenshot:
                # Create path for diff image
                diff_file = png_file.replace('.png', '-diff.png')

                diff_percentage = self.screenshot_manager.compare_screenshots(
                    png_file,
                    previous_screenshot,
                    diff_output_path=diff_file
                )

                if diff_percentage is not None:
                    # Extract date+serial from previous screenshot path
                    previous_date_serial = None
                    try:
                        parts = previous_screenshot.split(os.sep)
                        for part in parts:
                            if (len(part) == 10 or len(part) == 8) and part[:8].isdigit():
                                previous_date_serial = part
                                break
                    except:
                        pass

                    # Use threshold to determine if screenshots are identical
                    if diff_percentage > self.screenshot_manager.SSIM_THRESHOLD:
                        # Screenshots are identical or nearly identical, delete the new one and diff
                        os.remove(png_file)
                        if os.path.exists(diff_file):
                            os.remove(diff_file)
                        screenshot_kept = False
                        self.log.info(f"domain={domain} screenshot_similarity={diff_percentage*100:.2f}% action=deleted_identical")
                    else:
                        log_msg = f"domain={domain} screenshot_similarity={diff_percentage*100:.2f}%"
                        if previous_date_serial:
                            log_msg += f" previous_run={previous_date_serial}"
                        self.log.info(log_msg)

            # Calculate digest from page text
            digest = hashlib.sha256(page_text.encode('utf-8')).hexdigest()
            result = {
                'location': location,
                'code': status_code,
                'digest': digest
            }

            # Only include screenshot_similarity if screenshot was kept
            if diff_percentage is not None and screenshot_kept:
                result['screenshot_similarity'] = f"{diff_percentage:.2f}%"

            return result
        except Exception as ex:
            return {'code': str(ex)}
