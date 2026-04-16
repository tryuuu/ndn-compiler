from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from typing import Optional

from ndn.app import NDNApp
from ndn.encoding import Name, InterestParam, BinaryStr, FormalName
from ndn.security import KeychainDigest

logger = logging.getLogger(__name__)


def _extract_args(name: FormalName) -> list[str]:
    """Interest名から引数NDN名リストを抽出する。
    例: /modify/(/data/ryu-local/) → ["/data/ryu-local/"]
    ネストした括弧にも対応: /f/(/a, /g/(/b)) → ["/a", "/g/(/b)"]
    """
    decoded = Name.to_str(name)
    decoded = urllib.parse.unquote(decoded)

    # /t= メタデータを除去
    t_idx = decoded.rfind('/t=')
    if t_idx != -1:
        decoded = decoded[:t_idx]

    if '/(' not in decoded:
        return []

    start = decoded.find('/(') + 2
    args_str = decoded[start:-1]  # 末尾の ')' を除く

    args: list[str] = []
    depth = 0
    seg_start = 0
    for i, ch in enumerate(args_str):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            args.append(args_str[seg_start:i].strip())
            seg_start = i + 1
    args.append(args_str[seg_start:].strip())
    return [a for a in args if a]


class SeedServer:
    def __init__(self, prefix: str, app: NDNApp):
        self.prefix = prefix
        self.app = app
        # name → (content, content_type) のマップ
        self.server_map: dict[str, tuple[str, str]] = {}

    def run(self):
        @self.app.route(self.prefix)
        def on_interest(name: FormalName, param: InterestParam, app_param: Optional[BinaryStr]):
            if app_param:
                # ApplicationParameters あり → CREATE/DELETE コマンドとして処理
                asyncio.create_task(self._on_command(name, bytes(app_param)))
            else:
                # ApplicationParameters なし → 登録中サーバーの一覧を返す
                if self.server_map:
                    content = "\n".join(self.server_map.keys())
                else:
                    content = "no server created"
                # freshness_period=0 でキャッシュさせない
                self.app.put_data(name, content=content.encode(), freshness_period=0)
                logger.info(f"Returned server list: {list(self.server_map.keys())}")

        logger.info(f"Seed server started on {self.prefix}")
        self.app.run_forever()

    async def _on_command(self, name: FormalName, raw: bytes):
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in ApplicationParameters: {e}")
            return

        if not isinstance(req, dict):
            logger.error("ApplicationParameters is not a JSON object")
            return

        cmd_type = req.get("type")
        cmd_name: str = req.get("name", "")

        if not cmd_name.startswith("/"):
            cmd_name = "/" + cmd_name

        if cmd_type == "CREATE":
            content = req.get("content", "")
            content_type = req.get("content_type", "static")  # "static" or "ndn"
            if not content:
                logger.warning("CREATE missing 'content' field")
                return
            await self._create(cmd_name, content, content_type)
            self.app.put_data(name, content=f"created: {cmd_name}".encode(), freshness_period=10000)

        elif cmd_type == "DELETE":
            self._delete(cmd_name)
            self.app.put_data(name, content=f"deleted: {cmd_name}".encode(), freshness_period=10000)

        else:
            logger.warning(f"Unknown command type: {cmd_type!r}")

    async def _create(self, name: str, content: str, content_type: str = "static"):
        """仮想サーバーを作成し NFD にプレフィックスを動的に登録する。
        content_type="ndn" のとき、content を .ndn コードとして Interest ごとに実行する。
        content_type="static" のとき、content をそのまま返す。
        """
        self.server_map[name] = (content, content_type)
        logger.info(f"Creating server: {name!r}  content_type: {content_type!r}")

        if content_type == "ndn":
            def handler(int_name: FormalName, param: InterestParam, app_param: Optional[BinaryStr]):
                decoded = Name.to_str(int_name)
                if decoded.rstrip('/').endswith('/code'):
                    # コード取得リクエスト: .ndn ソースをそのまま返す
                    entry = self.server_map.get(name)
                    src = entry[0].encode() if entry else b""
                    self.app.put_data(int_name, content=src, freshness_period=0)
                    logger.info(f"Returned source for {name!r}")
                else:
                    asyncio.create_task(self._run_ndn(int_name, name))
        else:
            def handler(int_name: FormalName, param: InterestParam, app_param: Optional[BinaryStr]):
                logger.info(f"Interest for {Name.to_str(int_name)}")
                entry = self.server_map.get(name)
                data = entry[0].encode() if entry else b""
                self.app.put_data(int_name, content=data, freshness_period=10000)

        await self.app.register(name, handler)
        logger.info(f"Server registered: {name!r}")

    async def _run_ndn(self, int_name: FormalName, server_name: str):
        """.ndn コードを実行し結果を Data として返す。"""
        from ndnc.parser.parser import parse
        from ndnc.interp.evaluator import Interpreter

        entry = self.server_map.get(server_name)
        if entry is None:
            logger.warning(f"No entry for {server_name!r}")
            return

        ndn_code, _ = entry
        args = _extract_args(int_name)
        arg_dict = {f"arg{i}": v for i, v in enumerate(args)}

        logger.info(f"Running .ndn for {Name.to_str(int_name)}  args={arg_dict}")

        try:
            program = parse(ndn_code)
            interp = Interpreter(args=arg_dict)
            result = await interp.exec_in_context(program, self.app)
            logger.info(f"Result: {result!r}")
            self.app.put_data(int_name, content=result.encode(), freshness_period=10000)
        except Exception as e:
            logger.error(f"Error running .ndn: {e}")
            self.app.put_data(int_name, content=f"error: {e}".encode(), freshness_period=10000)

    def _delete(self, name: str):
        """仮想サーバーをマップから削除する。"""
        if name in self.server_map:
            del self.server_map[name]
            logger.info(f"Server deleted: {name!r}")
        else:
            logger.warning(f"No such server: {name!r}")
