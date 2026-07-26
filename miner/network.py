import requests
import json
import time
import logging
from config import RPC_URL, RPC_USER, RPC_PASSWORD

# Never let a stuck node block the miner forever.
RPC_TIMEOUT_SECONDS = 60


class BitcoindClient:
    def __init__(self):
        self.url = RPC_URL
        self.headers = {'content-type': 'application/json'}
        self.auth = (RPC_USER, RPC_PASSWORD)
        self.id_counter = 0
        # Reason the last call returned None (transport failure or JSON-RPC error).
        # None means the last call succeeded.
        self.last_error = None

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
                self.url, data=json.dumps(payload), headers=self.headers,
                auth=self.auth, timeout=RPC_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
        except requests.exceptions.RequestException as e:
            self.last_error = f"{method}: {e}"
            logging.warning(f"RPC transport error: {self.last_error}")
            return None
        except ValueError as e:
            self.last_error = f"{method}: invalid JSON response ({e})"
            logging.warning(f"RPC error: {self.last_error}")
            return None

        # A JSON-RPC error carries the *reason* (node syncing, bad params, ...).
        # Dropping it is what made a non-mining miner look like a working one.
        error = body.get('error')
        if error:
            if isinstance(error, dict):
                self.last_error = f"{method}: {error.get('message', error)} (code {error.get('code')})"
            else:
                self.last_error = f"{method}: {error}"
            return None

        self.last_error = None
        return body.get('result')

    def get_block_template(self):
        return self._call("getblocktemplate", [{"rules": ["segwit"]}])

    def submit_block(self, hex_data):
        return self._call("submitblock", [hex_data])

    def get_blockchain_info(self):
        return self._call("getblockchaininfo")

    def validate_address(self, address):
        return self._call("validateaddress", [address])
