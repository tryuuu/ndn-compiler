"""seed に remote_modify 関数を配置するセットアップスクリプト。
エンドツーエンドテストの前に実行する。"""
import asyncio
import json
import time
from ndn.app import NDNApp
from ndn.security import KeychainDigest

app = NDNApp(keychain=KeychainDigest())

# seed に配置する .ndn 関数の本体
# arg0 の NDN 名からデータを取得し、" modified" を付けて返す
REMOTE_MODIFY_CODE = 'let data = interest arg0\nlet result = concat(data, " modified")\nprint result'


async def main():
    params = {
        "type": "CREATE",
        "name": "/remote_modify",
        "content_type": "ndn",
        "content": REMOTE_MODIFY_CODE,
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
        result = bytes(content).decode() if content else "(empty)"
        print(f"[setup] {result}")
        print(f"[setup] remote_modify .ndn code:")
        for line in REMOTE_MODIFY_CODE.splitlines():
            print(f"         {line}")
    except Exception as e:
        print(f"[setup] ERROR: {e}")
    finally:
        app.shutdown()


app.run_forever(after_start=main())
