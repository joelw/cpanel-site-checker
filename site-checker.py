#!/usr/bin/env python3

import requests
import yaml
import logging
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from urllib.parse import urlparse, urljoin
import socket
import time
import urllib3
from PIL import Image
import glob


class WhmChecker:
    def __init__(self, config=None):
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
        self.ip_whitelist = []
        self.lastrun_file = config.get('lastrun_file', 'lastrun.txt')
        
        # Set up Selenium with Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=chrome_options)
        
        self.read_timeout = 30
        self.connect_timeout = 30
    
    def __del__(self):
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass
    
    def check_accounts(self, host, hash_key, date=None):
        if date is None:
            date = datetime.now().strftime(self.directory_format)
        
        # Set up WHM API connection
        base_url = f"https://{host}:2087"
        headers = {
            'Authorization': f'WHM root:{hash_key}'
        }
        
        directory = os.path.join(self.output_dir, date, host)
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Get list of accounts
        try:
            response = requests.get(
                f"{base_url}/json-api/listaccts",
                headers=headers,
                verify=False,
                timeout=self.read_timeout
            )
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            self.log.error(f"Failed to list accounts: {e}")
            sys.exit(1)
        
        # Get list of IP addresses for this server
        try:
            response = requests.get(
                f"{base_url}/json-api/listips",
                headers=headers,
                verify=False,
                timeout=self.read_timeout
            )
            response.raise_for_status()
            ip_result = response.json()
            
            if 'data' in ip_result and 'result' in ip_result['data']:
                ip_list = ip_result['data']['result']
                if isinstance(ip_list, list):
                    self.ip_whitelist = [item['ip'] for item in ip_list]
                else:
                    self.ip_whitelist = [ip_list['ip']]
        except Exception as e:
            self.log.error(f"server.list_ips: {e}")
            sys.exit(1)
        
        # Process each account
        if 'data' in result and 'acct' in result['data']:
            accounts = result['data']['acct']
        else:
            accounts = []
        
        for acct in accounts:
            if acct.get('suspended'):
                continue
            
            username = acct['user']
            
            # Get addon domains for this account
            domlist = []
            try:
                response = requests.get(
                    f"{base_url}/json-api/cpanel",
                    headers=headers,
                    params={
                        'cpanel_jsonapi_user': username,
                        'cpanel_jsonapi_module': 'AddonDomain',
                        'cpanel_jsonapi_func': 'listaddondomains',
                        'cpanel_jsonapi_apiversion': '2'
                    },
                    verify=False,
                    timeout=self.read_timeout
                )
                response.raise_for_status()
                addon_result = response.json()
                
                if 'cpanelresult' in addon_result and 'data' in addon_result['cpanelresult']:
                    domlist = addon_result['cpanelresult']['data']
            except Exception as e:
                self.log.warning(f"host={host} user={username} error=could_not_fetch_addons")
            
            # Add the main domain to the list
            domains = []
            all_domains = [acct] + domlist
            
            for account_domain in all_domains:
                domain = account_domain.get('domain')
                if not domain:
                    continue
                
                result, message = self.check_in_whitelist(domain)
                if result:
                    domains.append(domain)
                else:
                    self.log.warning(f"host={host} user={username} domain={domain} code={message}")
            
            # Fetch each domain
            for dom in domains:
                result = self.fetch_page(username, dom, directory)
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
    
    def check_in_whitelist(self, domain):
        try:
            ip = socket.gethostbyname(domain)
        except socket.gaierror:
            return False, "unresolvable"
        
        if ip in self.ip_whitelist:
            return True, None
        else:
            return False, "not_whitelisted"
    
    def resize_screenshot(self, image_path, width=500):
        """Resize screenshot to thumbnail with specified width, maintaining aspect ratio."""
        try:
            img = Image.open(image_path)
            
            # Guard against division by zero
            if img.width == 0:
                self.log.error(f"Invalid image width (0) for {image_path}")
                return False
            
            # Calculate new height to maintain aspect ratio
            aspect_ratio = img.height / img.width
            new_height = int(width * aspect_ratio)
            # Resize the image
            img_resized = img.resize((width, new_height), Image.LANCZOS)
            # Save back to the same file
            img_resized.save(image_path)
            return True
        except Exception as e:
            self.log.error(f"Failed to resize screenshot {image_path}: {e}")
            return False
    
    def find_previous_screenshot(self, domain, current_directory):
        """Find the most recent screenshot for a domain from previous runs.
        
        Expects directory structure: output_dir/date/host/username-domain.png
        """
        # Parse the current directory to get the base path
        base_output_dir = self.output_dir
        
        # Get all subdirectories in output_dir
        pattern = os.path.join(base_output_dir, '*', '*', f'*-{domain}.png')
        matching_files = glob.glob(pattern)
        
        # Filter out the current directory's file
        matching_files = [f for f in matching_files if not f.startswith(current_directory)]
        
        if not matching_files:
            return None
        
        # Sort by modification time, most recent first
        matching_files.sort(key=os.path.getmtime, reverse=True)
        return matching_files[0]
    
    def compare_screenshots(self, img1_path, img2_path):
        """Compare two screenshots and return the percentage of different pixels."""
        try:
            img1 = Image.open(img1_path)
            img2 = Image.open(img2_path)
            
            # Ensure both images are the same size
            # This handles cases where previous screenshots were captured before resize feature
            if img1.size != img2.size:
                # Resize img2 to match img1 if they differ
                img2 = img2.resize(img1.size, Image.LANCZOS)
            
            # Convert to RGB if needed (in case of RGBA or other formats)
            if img1.mode != 'RGB':
                img1 = img1.convert('RGB')
            if img2.mode != 'RGB':
                img2 = img2.convert('RGB')
            
            # Get pixel data
            pixels1 = list(img1.getdata())
            pixels2 = list(img2.getdata())
            
            # Count different pixels
            different_pixels = sum(1 for p1, p2 in zip(pixels1, pixels2) if p1 != p2)
            total_pixels = len(pixels1)
            
            # Calculate percentage
            if total_pixels > 0:
                diff_percentage = (different_pixels / total_pixels) * 100
            else:
                diff_percentage = 0
            
            return diff_percentage
        except Exception as e:
            self.log.error(f"Failed to compare screenshots: {e}")
            return None
    
    def fetch_page(self, user, domain, directory):
        url = f"http://{domain}"
        
        html_file = os.path.join(directory, f"{user}-{domain}.html")
        png_file = os.path.join(directory, f"{user}-{domain}.png")
        
        if os.path.exists(html_file) and os.path.exists(png_file):
            return {'code': 'skipped'}
        
        try:
            location, response = self.fetch_url(url)
            
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
            self.driver.get(location)
            self.driver.set_window_size(1440, 2000)
            self.driver.save_screenshot(png_file)
            
            # Resize screenshot to 500px width thumbnail
            self.resize_screenshot(png_file, width=500)
            
            # Find previous screenshot and compare
            previous_screenshot = self.find_previous_screenshot(domain, directory)
            diff_percentage = None
            
            if previous_screenshot:
                diff_percentage = self.compare_screenshots(png_file, previous_screenshot)
                
                if diff_percentage is not None:
                    # Use a small epsilon for floating-point comparison
                    if diff_percentage < 0.01:
                        # Screenshots are identical or nearly identical, delete the new one
                        os.remove(png_file)
                        self.log.info(f"domain={domain} screenshot_diff={diff_percentage:.2f}% action=deleted_identical")
                    else:
                        self.log.info(f"domain={domain} screenshot_diff={diff_percentage:.2f}%")
            
            digest = hashlib.sha256(response.content).hexdigest()
            result = {
                'location': location,
                'code': response.status_code,
                'digest': digest
            }
            
            if diff_percentage is not None:
                result['screenshot_diff'] = f"{diff_percentage:.2f}%"
            
            return result
        except Exception as ex:
            return {'code': str(ex)}
    
    def fetch_url(self, url, limit=5):
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


def main():
    configfile = 'servers.yml'
    
    if not os.path.exists(configfile):
        print(f"Error: {configfile} not found. Please create it from servers.yml.sample")
        sys.exit(1)
    
    with open(configfile, 'r') as f:
        config = yaml.safe_load(f)
    
    # Disable SSL warnings for self-signed certificates
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    whm = WhmChecker(config.get('config', {}))
    
    servers = config.get('servers', [])
    for server in servers:
        whm.check_accounts(server['host'], server['hash'])


if __name__ == '__main__':
    main()
