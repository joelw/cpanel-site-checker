"""WHM API client for interacting with cPanel/WHM servers."""

import requests
import logging


class WhmApiClient:
    """Client for interacting with WHM API."""

    def __init__(self, host, hash_key, read_timeout=30):
        """Initialize WHM API client.

        Args:
            host: WHM server hostname
            hash_key: WHM API token/hash key
            read_timeout: Request timeout in seconds
        """
        self.host = host
        self.base_url = f"https://{host}:2087"
        self.headers = {
            'Authorization': f'WHM root:{hash_key}'
        }
        self.read_timeout = read_timeout
        self.log = logging.getLogger(__name__)

    def list_accounts(self):
        """List all cPanel accounts on the server.

        Returns:
            list: List of account dictionaries

        Raises:
            Exception: If API call fails
        """
        try:
            response = requests.get(
                f"{self.base_url}/json-api/listaccts",
                headers=self.headers,
                verify=False,
                timeout=self.read_timeout
            )
            response.raise_for_status()
            result = response.json()

            if 'acct' in result:
                return result['acct']
            return []
        except Exception as e:
            self.log.error(f"Failed to list accounts: {e}")
            raise

    def list_ips(self):
        """List all IP addresses on the server.

        Returns:
            list: List of IP addresses

        Raises:
            Exception: If API call fails
        """
        try:
            response = requests.get(
                f"{self.base_url}/json-api/listips",
                headers=self.headers,
                verify=False,
                timeout=self.read_timeout
            )
            response.raise_for_status()
            ip_result = response.json()

            if 'result' in ip_result:
                ip_list = ip_result['result']
                if isinstance(ip_list, list):
                    return [item['ip'] for item in ip_list]
                else:
                    return [ip_list['ip']]
            return []
        except Exception as e:
            self.log.error(f"Failed to list IPs: {e}")
            raise

    def list_addon_domains(self, username):
        """List addon domains for a specific cPanel account.

        Args:
            username: cPanel username

        Returns:
            list: List of addon domain dictionaries
        """
        try:
            response = requests.get(
                f"{self.base_url}/json-api/cpanel",
                headers=self.headers,
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
                return addon_result['cpanelresult']['data']
            return []
        except Exception as e:
            self.log.warning(f"Could not fetch addon domains for user {username}: {e}")
            return []
