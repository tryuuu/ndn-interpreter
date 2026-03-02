import urllib.parse
from typing import Optional
from ndn.app import NDNApp
from ndn.encoding import Name, InterestParam, BinaryStr, FormalName
from ndn.security import KeychainDigest

import logging
logging.basicConfig(format='[{asctime}]{levelname}:{message}',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO,
                    style='{')

PREFIX = '/remote_modify'

app = NDNApp(keychain=KeychainDigest())


def extract_arg(name: FormalName) -> str:
    """NDN 名 /remote_modify/<arg> から引数を取り出す"""
    name_str = urllib.parse.unquote(Name.to_str(name))
    # /t= などメタデータを除去
    t_idx = name_str.rfind('/t=')
    if t_idx != -1:
        name_str = name_str[:t_idx]
    # /remote_modify/<arg> の <arg> を返す
    parts = name_str.split('/', maxsplit=2)
    return parts[2] if len(parts) >= 3 else ''


@app.route(PREFIX)
def on_interest(name: FormalName, param: InterestParam, _app_param: Optional[BinaryStr]):
    arg = extract_arg(name)
    result = f"{arg} from remote_modify"
    print(f">> remote_modify called: arg={arg!r}, result={result!r}")
    app.put_data(name, content=result.encode(), freshness_period=10000)


if __name__ == '__main__':
    print(f"Starting remote_modify function node on {PREFIX}")
    app.run_forever()
