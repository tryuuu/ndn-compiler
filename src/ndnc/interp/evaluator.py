from __future__ import annotations
from typing import Any, Union, Optional
import asyncio
import contextlib
import io
import json
import time
import traceback
import sys
from pathlib import Path
from ndn.app import NDNApp
from ndn.encoding import Name
from ndn.security import KeychainDigest
from ..parser.ast import (
	Program, PrintStatement, Assignment, ExprStatement,
	StringLiteral, NumberLiteral, Variable,
	ExpressInterest, FunctionCall, BinOp, UnaryOp, Expr
)

# ローカルで処理できる関数名のセット
_LOCAL_FUNCTIONS = {"modify", "concat", "m_to_feet"}

_CACHE_DIR = Path.home() / ".ndnc" / "cache"
_CACHE_TTL = 300  # seconds


def _cache_path(func_name: str) -> Path:
    safe = func_name.lstrip("/").replace("/", "_")
    return _CACHE_DIR / f"{safe}.json"


def _load_cache(func_name: str) -> Optional[str]:
    """キャッシュが有効なら .ndn ソースを返す。期限切れ・未存在なら None。"""
    path = _cache_path(func_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data["cached_at"] > _CACHE_TTL:
            return None
        return data["code"]
    except Exception:
        return None


def _save_cache(func_name: str, code: str) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(func_name)
    path.write_text(json.dumps({"code": code, "cached_at": time.time()}))


def _interest_cache_path(ndn_name: str) -> Path:
    safe = "interest_" + ndn_name.strip("/").replace("/", "_")
    return _CACHE_DIR / f"{safe}.json"


def _load_interest_cache(ndn_name: str) -> Optional[Any]:
    """interest キャッシュが有効なら値を返す。期限切れ・未存在なら None。"""
    path = _interest_cache_path(ndn_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data["cached_at"] > _CACHE_TTL:
            return None
        return data["value"]
    except Exception:
        return None


def _save_interest_cache(ndn_name: str, value: Any) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _interest_cache_path(ndn_name)
    path.write_text(json.dumps({"value": value, "cached_at": time.time()}))

class Interpreter:
    # プロセス内で共有するメモリキャッシュ（関数名 → .ndn コード）
    _code_cache: dict[str, str] = {}
    # プロセス内で共有するメモリキャッシュ（NDN 名 → 取得済みデータ）
    _interest_cache: dict[str, Any] = {}

    def __init__(self, args: dict[str, str] | None = None):
        self._env: dict[str, Any] = {}
        self._env_origin: dict[str, str] = {}  # interest で取得した変数の NDN 名を追跡
        # 外部から渡された引数を env に事前登録（例: {"arg0": "/data/ryu-local/"}）
        if args:
            self._env.update(args)
        self.app: Optional[NDNApp] = None
        self._local_data: dict[str, str] = {
            '/data/ryu-local/': 'local data',
            '/height/Mt.Fuji/': '3776m',
        }

    def run(self, program: Program):
        has_interest = any(
            (isinstance(st, ExprStatement) and self._has_interest(st.expr)) or
            (isinstance(st, PrintStatement) and self._has_interest(st.expr)) or
            (isinstance(st, Assignment) and self._has_interest(st.expr))
            for st in program
        )

        if has_interest:
            try:
                self.app = NDNApp(keychain=KeychainDigest())
                # ローカルデータを NDN プロデューサーとして登録する
                # （リモート関数がこれらをフェッチできるようにするため）
                self._register_local_data_routes()

                async def after_start():
                    try:
                        await self._exec_block(program)
                    except Exception:
                        traceback.print_exc()
                        raise
                    finally:
                        self.app.shutdown()

                self.app.run_forever(after_start=after_start())

            except Exception:
                self.app = None
                asyncio.run(self._exec_block(program))
        else:
            asyncio.run(self._exec_block(program))

    def _has_interest(self, expr: Expr) -> bool:
        if isinstance(expr, ExpressInterest):
            if expr.name_is_var:
                # 変数の値は実行時まで不明なのでネットワーク必要とみなす
                return True
            # _local_data にあればネットワーク不要
            return expr.name not in self._local_data
        if isinstance(expr, Variable):
            return False
        if isinstance(expr, FunctionCall):
            # ローカルにない関数はリモート呼び出しになるため NDNApp が必要
            return (expr.name not in _LOCAL_FUNCTIONS) or any(self._has_interest(a) for a in expr.args)
        return False

    async def _exec_block(self, node: Program):
        for st in node:
            if isinstance(st, PrintStatement):
                await self._exec_print(st)
            elif isinstance(st, Assignment):
                await self._exec_assignment(st)
            elif isinstance(st, ExprStatement):
                await self._exec_expr_stmt(st)
            else:
                raise RuntimeError(f"Unsupported node: {st}")

    async def _exec_print(self, node: PrintStatement):
        value = await self._eval_expr(node.expr)
        print(value)

    async def _exec_assignment(self, node: Assignment):
        value = await self._eval_expr(node.expr)
        self._env[node.name] = value
        # interest で取得した変数は NDN 名を記録しておく
        if isinstance(node.expr, ExpressInterest):
            if node.expr.name_is_var:
                # 変数名から実際の NDN 名を解決して記録
                ndn_name = self._env.get(node.expr.name, "")
                self._env_origin[node.name] = str(ndn_name)
            else:
                self._env_origin[node.name] = node.expr.name

    async def _exec_expr_stmt(self, node: ExprStatement):
        value = await self._eval_expr(node.expr)
        print(value)

    async def _eval_expr(self, expr: Expr) -> Union[int, str]:
        if isinstance(expr, StringLiteral):
            return expr.value

        if isinstance(expr, NumberLiteral):
            return expr.value

        if isinstance(expr, Variable):
            if expr.name not in self._env:
                raise RuntimeError(f"Variable '{expr.name}' is not defined")
            return self._env[expr.name]

        if isinstance(expr, ExpressInterest):
            # name_is_var のとき、変数から実際の NDN 名を解決する
            if expr.name_is_var:
                if expr.name not in self._env:
                    raise RuntimeError(f"Variable '{expr.name}' is not defined (used in interest)")
                ndn_name = str(self._env[expr.name])
            else:
                ndn_name = expr.name

            if not ndn_name.startswith('/'):
                ndn_name = '/' + ndn_name
            if not ndn_name.endswith('/'):
                ndn_name = ndn_name + '/'

            if ndn_name in self._local_data:
                local_value = self._local_data[ndn_name]
                try:
                    return int(local_value)
                except ValueError:
                    return local_value

            if self.app is None:
                return f"mock_{ndn_name.replace('/', '_')}"

            # 1. メモリキャッシュ確認
            if ndn_name in Interpreter._interest_cache:
                return Interpreter._interest_cache[ndn_name]

            # 2. ファイルキャッシュ確認
            file_cached = _load_interest_cache(ndn_name)
            if file_cached is not None:
                Interpreter._interest_cache[ndn_name] = file_cached
                return file_cached

            # 3. ネットワーク取得
            try:
                _, _, content = await self.app.express_interest(
                    ndn_name,
                    must_be_fresh=True,
                    can_be_prefix=True,
                    lifetime=6000
                )
                if content is None:
                    return ""
                text = bytes(content).decode('utf-8').strip()
                try:
                    value = int(text)
                except ValueError:
                    value = text
                Interpreter._interest_cache[ndn_name] = value
                _save_interest_cache(ndn_name, value)
                print(f"[ndnc] cached interest '{ndn_name}' (~/.ndnc/cache/)", file=sys.stderr)
                return value
            except Exception as e:
                print(f"Error expressing interest for {expr.name}: {e}")
                raise e

        if isinstance(expr, FunctionCall):
            if expr.name in _LOCAL_FUNCTIONS:
                arg_values = [await self._eval_expr(a) for a in expr.args]
                if expr.name == "m_to_feet":
                    meters_str = str(arg_values[0]).rstrip('m')
                    feet = round(float(meters_str) * 3.28084)
                    return f"{feet}ft"
                if expr.name == "concat":
                    return "".join(str(v) for v in arg_values)
                return str(arg_values[0]) + " from function"
            elif self.app is not None:
                # リモート関数: 引数を NDN 名として渡す（ネストした関数呼び出しも再帰的に解決）
                ndn_names = [self._to_ndn_name(a) for a in expr.args]
                return await self._call_remote_function(expr.name, ndn_names)
            else:
                raise RuntimeError(f"Unknown function: {expr.name}")

        if isinstance(expr, BinOp):
            left = await self._eval_expr(expr.left)
            right = await self._eval_expr(expr.right)
            left_n = float(left)
            right_n = float(right)
            if expr.op == "+":
                result = left_n + right_n
            elif expr.op == "-":
                result = left_n - right_n
            elif expr.op == "*":
                result = left_n * right_n
            elif expr.op == "/":
                if right_n == 0:
                    raise RuntimeError("Division by zero")
                result = left_n / right_n
            else:
                raise RuntimeError(f"Unknown operator: {expr.op}")
            # 整数に落とせるなら int で返す
            return int(result) if result == int(result) else result

        if isinstance(expr, UnaryOp):
            val = await self._eval_expr(expr.operand)
            if expr.op == "-":
                n = float(val)
                result = -n
                return int(result) if result == int(result) else result
            raise RuntimeError(f"Unknown unary operator: {expr.op}")

        raise RuntimeError(f"Unsupported expr: {expr}")

    def _register_local_data_routes(self):
        """ローカルデータを NDN プロデューサーとして登録する。
        リモート関数がフェッチできるよう、Interest に応答できるようにする。"""
        for ndn_name, value in self._local_data.items():
            prefix = ndn_name.rstrip('/')
            val_bytes = str(value).encode()

            def make_handler(content):
                def handler(name, param, app_param):
                    self.app.put_data(name, content=content, freshness_period=10000)
                return handler

            self.app.route(prefix)(make_handler(val_bytes))

    def _to_ndn_name(self, expr: Expr) -> str:
        """リモート関数の引数として使う NDN 名を決定する。
        - ExpressInterest → そのまま NDN 名を返す
        - Variable → interest 由来なら記録済みの NDN 名、そうでなければ値を NDN 名として扱う
        - StringLiteral → 先頭 '/' を補完して NDN 名とする"""
        if isinstance(expr, ExpressInterest):
            if expr.name_is_var:
                if expr.name in self._env_origin:
                    return self._env_origin[expr.name]
                val = self._env.get(expr.name, "")
                return str(val) if str(val).startswith('/') else '/' + str(val)
            return expr.name
        if isinstance(expr, Variable):
            if expr.name in self._env_origin:
                return self._env_origin[expr.name]
            val = self._env.get(expr.name, "")
            if isinstance(val, str):
                return val if val.startswith('/') else '/' + val
            return str(val)
        if isinstance(expr, NumberLiteral):
            return str(expr.value)
        if isinstance(expr, StringLiteral):
            val = expr.value
            return val if val.startswith('/') else '/' + val
        if isinstance(expr, FunctionCall):
            if expr.name not in _LOCAL_FUNCTIONS:
                ndn_names = [self._to_ndn_name(a) for a in expr.args]
                args_str = ", ".join(ndn_names)
                return "/" + expr.name + "/(" + args_str + ")"
        return str(expr)

    async def _call_remote_function(self, func_name: str, ndn_names: list[str]) -> str:
        # 1. メモリキャッシュ確認（最速）
        if func_name in Interpreter._code_cache:
            return await self._run_cached(func_name, Interpreter._code_cache[func_name], ndn_names)

        # 2. ファイルキャッシュ確認（TTL チェックあり）
        cached_code = _load_cache(func_name)
        if cached_code is not None:
            Interpreter._code_cache[func_name] = cached_code  # メモリにも載せる
            return await self._run_cached(func_name, cached_code, ndn_names)

        # 3. キャッシュミス: seed から .ndn ソースを取得
        code = await self._fetch_function_code(func_name)
        if code is not None:
            Interpreter._code_cache[func_name] = code  # メモリに保存
            _save_cache(func_name, code)               # ファイルに保存
            print(f"[ndnc] cached '{func_name}' (~/.ndnc/cache/)", file=sys.stderr)
            return await self._run_cached(func_name, code, ndn_names)

        # 4. コード取得失敗: 従来通り seed に実行を委ねる
        args_str = ", ".join(ndn_names)
        interest_name = "/" + func_name + "/(" + args_str + ")"
        try:
            _, _, content = await self.app.express_interest(
                interest_name,
                must_be_fresh=True,
                can_be_prefix=False,
                lifetime=20000,
            )
            if content is None:
                return ""
            return bytes(content).decode('utf-8').strip()
        except Exception as e:
            print(f"Error calling remote function '{func_name}': {e}")
            raise

    async def _fetch_function_code(self, func_name: str) -> Optional[str]:
        """seed から /func_name/code を取得して .ndn ソースを返す。失敗時は None。"""
        interest_name = "/" + func_name + "/code"
        try:
            _, _, content = await self.app.express_interest(
                interest_name,
                must_be_fresh=True,
                can_be_prefix=False,
                lifetime=6000,
            )
            if content is None:
                return None
            return bytes(content).decode('utf-8').strip()
        except Exception:
            return None

    async def _run_cached(self, func_name: str, code: str, ndn_names: list[str]) -> str:
        """キャッシュ済み .ndn コードを引数付きでローカル実行する。"""
        from ..parser.parser import parse
        arg_dict = {f"arg{i}": v for i, v in enumerate(ndn_names)}
        program = parse(code)
        interp = Interpreter(args=arg_dict)
        interp.app = self.app
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            await interp._exec_block(program)
        return buffer.getvalue().strip()

    async def exec_in_context(self, program: Program, app: NDNApp) -> str:
        """既存の NDNApp のコンテキスト内で .ndn プログラムを実行し、出力を文字列で返す。
        seed サーバーなど、すでにイベントループが動いている環境から呼び出す用途向け。
        通常の run() と異なり、新たなイベントループや NDNApp を起動しない。"""
        self.app = app
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            await self._exec_block(program)
        return buffer.getvalue().strip()
