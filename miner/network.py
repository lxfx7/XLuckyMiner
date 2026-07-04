import requests
import json
import time
from config import RPC_URL, RPC_USER, RPC_PASSWORD

class BitcoindClient:
    def __init__(self):
        self.url = RPC_URL
        self.headers = {'content-type': 'application/json'}
        self.auth = (RPC_USER, RPC_PASSWORD)
        self.id_counter = 0

    def _call(self, method, params=[]):
        self.id_counter += 1
        payload = {
            "method": method,
            "params": params,
            "jsonrpc": "2.0",
            "id": self.id_counter
        }
        try:
            response = requests.post(
                self.url, data=json.dumps(payload), headers=self.headers, auth=self.auth
            )
            response.raise_for_status()
            return response.json().get('result')
        except requests.exceptions.RequestException as e:
            print(f"RPC Error: {e}")
            return None

    def get_block_template(self):
        return self._call("getblocktemplate", [{"rules": ["segwit"]}])

    def submit_block(self, hex_data):
        return self._call("submitblock", [hex_data])

    def get_blockchain_info(self):
        return self._call("getblockchaininfo")

    def validate_address(self, address):
        return self._call("validateaddress", [address])
