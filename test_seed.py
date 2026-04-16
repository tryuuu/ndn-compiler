"""seed サーバーの動作確認スクリプト"""
import asyncio
import json
import time
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest

app = NDNApp(keychain=KeychainDigest())

async def send_interest(name: str, params: dict | None = None, bypass_cache: bool = False):
    # bypass_cache=True のときタイムスタンプコンポーネントを付けてNFD CSをバイパス
    actual_name = f"{name}/t={int(time.time()*1000)}" if bypass_cache else name
    kwargs = dict(must_be_fresh=True, can_be_prefix=False, lifetime=4000)
    if params:
        # タイムスタンプを加えてInterestを毎回ユニークにし、NFD CSのキャッシュをバイパスする
        params_with_ts = {**params, "_ts": int(time.time() * 1000)}
        kwargs["app_param"] = json.dumps(params_with_ts).encode()
        kwargs["must_be_fresh"] = False

    try:
        _, _, content = await app.express_interest(actual_name, **kwargs)
        result = bytes(content).decode() if content else "(empty)"
        print(f"[OK] {name} -> {result!r}")
        return result
    except Exception as e:
        print(f"[NG] {name} -> {e}")
        return None


async def main():
    # 1. サーバー一覧を確認（最初は空）
    print("=== 1. LIST (empty) ===")
    await send_interest("/seed", bypass_cache=True)

    # 2. 静的サーバー /hello を CREATE
    print("\n=== 2. CREATE /hello (static) ===")
    await send_interest("/seed", {"type": "CREATE", "name": "/hello", "content": "hello from seed"})

    # 3. .ndn 関数 /ndn_echo を CREATE
    #    arg0 の NDN 名からデータを取得してそのまま返す .ndn コード
    ndn_code = "let data = interest arg0\nprint data"
    print("\n=== 3. CREATE /ndn_echo (ndn) ===")
    await send_interest("/seed", {
        "type": "CREATE",
        "name": "/ndn_echo",
        "content_type": "ndn",
        "content": ndn_code,
    })

    # 4. サーバー一覧を確認
    print("\n=== 4. LIST ===")
    await send_interest("/seed", bypass_cache=True)

    # 5. 静的サーバーからデータ取得
    print("\n=== 5. GET /hello ===")
    await send_interest("/hello")

    # 6. .ndn 関数を引数付きで呼び出す
    #    /data/ryu-local/ は evaluator の _local_data に登録済み → "local data" が返るはず
    print("\n=== 6. GET /ndn_echo/(/data/ryu-local/) ===")
    await send_interest("/ndn_echo/(/data/ryu-local/)")

    # 7. /hello を DELETE
    print("\n=== 7. DELETE /hello ===")
    await send_interest("/seed", {"type": "DELETE", "name": "/hello"})

    # 8. サーバー一覧を確認
    print("\n=== 8. LIST after DELETE ===")
    await send_interest("/seed", bypass_cache=True)

    app.shutdown()


app.run_forever(after_start=main())
