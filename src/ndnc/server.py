from __future__ import annotations

import sys

from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest


class Server:
    def __init__(self):
        try:
            self.app = NDNApp(keychain=KeychainDigest())
        except Exception as e:
            print(f"Error: Failed to initialize NDNApp: {e}", file=sys.stderr)
            sys.exit(1)

    def run(self):
        @self.app.route('/data/ryu')
        def on_data_ryu(name, param, _app_param):
            print(f"Received Interest: {Name.to_str(name)}")
            self.app.put_data(name, content=b'success', freshness_period=10000)
            print(f"Sent Data: {Name.to_str(name)} -> success")
        print("Server started. Listening for Interests on /data/ryu...")

        @self.app.route('/data/nakazatolab')
        def on_data_nakazatolab(name, param, _app_param):
            print(f"Received Interest: {Name.to_str(name)}")
            self.app.put_data(name, content=b'NDN research', freshness_period=10000)
            print(f"Sent Data: {Name.to_str(name)} -> NDN research")
        print("Server started. Listening for Interests on /data/nakazatolab...")

        @self.app.route('/height/Mt.Fuji')
        def on_height_mt_fuji(name, param, _app_param):
            print(f"Received Interest: {Name.to_str(name)}")
            self.app.put_data(name, content=b'3776m', freshness_period=10000)
            print(f"Sent Data: {Name.to_str(name)} -> 3776m")
        print("Server started. Listening for Interests on /height/Mt.Fuji...")

        self.app.run_forever()
