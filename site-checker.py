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
            
            digest = hashlib.sha256(response.content).hexdigest()
            return {
                'location': location,
                'code': response.status_code,
                'digest': digest
            }
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
