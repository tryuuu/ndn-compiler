import json
import time
from ndn.app import NDNApp
from ndn.security import KeychainDigest

app = NDNApp(keychain=KeychainDigest())

CODE = 'let meters = interest arg0\nlet result = concat(meters * 3.28084, "ft")\nprint result'


async def main():
    params = {
        "type": "CREATE",
        "name": "/m_to_feet",
        "content_type": "ndn",
        "content": CODE,
        "_ts": int(time.time() * 1000),
    }
    try:
        _, _, content = await app.express_interest(
            "/seed",
            app_param=json.dumps(params).encode(),
            must_be_fresh=False,
            can_be_prefix=False,
            lifetime=4000,
        )
        print(bytes(content).decode() if content else "(empty)")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        app.shutdown()


app.run_forever(after_start=main())
