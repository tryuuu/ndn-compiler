import asyncio
import urllib.parse
from typing import Optional
from ndn.app import NDNApp
from ndn.encoding import Name, InterestParam, BinaryStr, FormalName
from ndn.security import KeychainDigest
from ndn.types import InterestNack, InterestTimeout

import logging
logging.basicConfig(format='[{asctime}]{levelname}:{message}',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO,
                    style='{')

_TEMPERATURE_DATA: dict[str, float] = {
    '/data/tokyo':   22.5,
    '/data/paris':   18.0,
    '/data/newyork': 15.3,
    '/data/london':  12.8,
    '/data/sydney':  26.1,
}

app = NDNApp(keychain=KeychainDigest())


def decode_and_remove_metadata(name: FormalName) -> str:
    """NDN FormalName をデコードし、/t= などのメタデータを除去して返す。"""
    decoded = Name.to_str(name)
    decoded = urllib.parse.unquote(decoded)
    # ')' の直後に '/' が続く場合はそこで打ち切る
    end = decoded.rfind(')')
    if end != -1 and len(decoded) > end + 1 and decoded[end + 1] == '/':
        decoded = decoded[:end + 1]
    # /t= メタデータを除去
    t_idx = decoded.rfind('/t=')
    if t_idx != -1:
        decoded = decoded[:t_idx]
    return decoded


def is_function_request(name: FormalName) -> bool:
    """/( が含まれていれば関数リクエストと判定する。"""
    return "/(" in decode_and_remove_metadata(name)


def extract_first_level_args(name: FormalName) -> list[str]:
    """関数 Interest から第一階層の引数（NDN 名）リストを取り出す。
    ネストした括弧にも対応。例: /f/(/a, /g/(/b)) → ['/a', '/g/(/b)']"""
    decoded = decode_and_remove_metadata(name)
    if '(' not in decoded:
        return [decoded.strip()]

    start_of_args = decoded.find('/(') + 2   # '(' の直後
    args_str = decoded[start_of_args:-1]      # 末尾の ')' を除く

    args: list[str] = []
    start = 0
    depth = 0
    for i, ch in enumerate(args_str):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            args.append(args_str[start:i].strip())
            start = i + 1
    args.append(args_str[start:].strip())
    return args


async def _fetch_arg(ndn_name: str) -> Optional[bytes]:
    """引数の NDN 名を解決する。
    ローカルデータストアを先に確認し、なければ consumer_app で Interest を発行する。
    引数がネストした関数呼び出しの場合も再帰的に解決される。"""
    key = ndn_name.rstrip('/')
    if key in _TEMPERATURE_DATA:
        logging.info(f"[local] {key} = {_TEMPERATURE_DATA[key]}")
        return str(_TEMPERATURE_DATA[key]).encode()

    # NDN ネットワーク経由で取得（ネストした関数呼び出しを含む）
    logging.info(f"[fetch] {ndn_name}")
    for attempt in range(3):
        try:
            _, _, content = await app.express_interest(
                ndn_name, must_be_fresh=True, can_be_prefix=False, lifetime=10000
            )
            if content:
                logging.info(f"[fetch] OK {ndn_name} (attempt {attempt + 1})")
                return bytes(content)
        except (InterestNack, InterestTimeout) as e:
            logging.warning(f"[fetch] {ndn_name} attempt {attempt + 1} failed: {e}")
        await asyncio.sleep(0.3)
    logging.error(f"[fetch] GIVE-UP {ndn_name}")
    return None


@app.route('/data')
def on_data(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    """データリクエストに応答する（/data/* プレフィックス）。"""
    name_str = Name.to_str(name)
    t_idx = name_str.rfind('/t=')
    if t_idx != -1:
        name_str = name_str[:t_idx]
    key = name_str.rstrip('/')
    if key in _TEMPERATURE_DATA:
        logging.info(f"Serving data: {key}")
        app.put_data(name, content=str(_TEMPERATURE_DATA[key]).encode(), freshness_period=10000)
    else:
        logging.warning(f"Unknown data key: {key}")


@app.route('/remote_modify')
def on_modify(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    async def handler():
        logging.info(f"Interest: {Name.to_str(name)}")
        if not is_function_request(name):
            logging.warning("Not a function request")
            return

        args = extract_first_level_args(name)
        logging.info(f"Args: {args}")

        contents = await asyncio.gather(*[_fetch_arg(a) for a in args])
        if any(c is None for c in contents):
            app.put_data(name, content=b"error: failed to fetch argument", freshness_period=10000)
            return

        result = f"{contents[0].decode()} from remote_modify"
        logging.info(f"Result: {result!r}")
        app.put_data(name, content=result.encode(), freshness_period=10000)

    asyncio.create_task(handler())


@app.route('/temperature_average')
def on_temperature_average(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    async def handler():
        logging.info(f"Interest: {Name.to_str(name)}")
        if not is_function_request(name):
            logging.warning("Not a function request")
            return

        args = extract_first_level_args(name)
        logging.info(f"Args: {args}")

        contents = await asyncio.gather(*[_fetch_arg(a) for a in args])
        if any(c is None for c in contents):
            app.put_data(name, content=b"error: failed to fetch argument(s)", freshness_period=10000)
            return

        try:
            temps = [float(c.decode()) for c in contents]
            average = sum(temps) / len(temps)
            result = f"{average:.1f}"
            logging.info(f"temperature_average{tuple(args)} = {result}")
            app.put_data(name, content=result.encode(), freshness_period=10000)
        except ValueError as e:
            app.put_data(name, content=f"error: {e}".encode(), freshness_period=10000)

    asyncio.create_task(handler())


@app.route('/format_temp')
def on_format_temp(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    async def handler():
        logging.info(f"Interest: {Name.to_str(name)}")
        if not is_function_request(name):
            logging.warning("Not a function request")
            return

        args = extract_first_level_args(name)
        logging.info(f"Args: {args}")

        contents = await asyncio.gather(*[_fetch_arg(a) for a in args])
        if any(c is None for c in contents):
            app.put_data(name, content=b"error: failed to fetch argument", freshness_period=10000)
            return

        result = f"{contents[0].decode()}°C"
        logging.info(f"Result: {result!r}")
        app.put_data(name, content=result.encode(), freshness_period=10000)

    asyncio.create_task(handler())


@app.route('/m_to_feet')
def on_m_to_feet(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    async def handler():
        logging.info(f"Interest: {Name.to_str(name)}")
        if not is_function_request(name):
            logging.warning("Not a function request")
            return

        args = extract_first_level_args(name)
        logging.info(f"Args: {args}")

        contents = await asyncio.gather(*[_fetch_arg(a) for a in args])
        if any(c is None for c in contents):
            app.put_data(name, content=b"error: failed to fetch argument", freshness_period=10000)
            return

        try:
            meters_str = contents[0].decode().rstrip('m')
            feet = round(float(meters_str) * 3.28084)
            result = f"{feet}ft"
            logging.info(f"Result: {result!r}")
            app.put_data(name, content=result.encode(), freshness_period=10000)
        except ValueError as e:
            app.put_data(name, content=f"error: {e}".encode(), freshness_period=10000)

    asyncio.create_task(handler())


if __name__ == '__main__':
    print("Starting remote function node")
    print(f"  /remote_modify       : /remote_modify/(<arg>)")
    print(f"  /temperature_average : /temperature_average/(<name1>, <name2>, ...)")
    print(f"  /format_temp         : /format_temp/(<temp_value_or_func>)")
    print(f"  /m_to_feet           : /m_to_feet/(<meters_value>)")
    print(f"  /data/*              : temperature data")
    print(f"  Available data: {list(_TEMPERATURE_DATA.keys())}")
    app.run_forever()
