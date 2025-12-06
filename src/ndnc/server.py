from __future__ import annotations

import sys

from ndn.app import NDNApp
from ndn.encoding import Name


class Server:
    def __init__(self):
        try:
            self.app = NDNApp()
        except Exception as e:
            print(f"Error: Failed to initialize NDNApp: {e}", file=sys.stderr)
            sys.exit(1)

    def run(self):
        @self.app.route('/data/ryu')
        def on_interest(name, param, _app_param):
            print(f"Received Interest: {Name.to_str(name)}")
            self.app.put_data(name, content=b'success', freshness_period=10000)
            print(f"Sent Data: {Name.to_str(name)} -> success")

        print("Server started. Listening for Interests on /data/ryu...")
        self.app.run_forever()
