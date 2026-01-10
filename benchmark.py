import time
import subprocess
import socket
import urllib.request
import os

NDN_FILE = "examples/hello.ndn"

def measure_ndnc(label, interest_name):
    """ndncコマンドの実行時間を計測する（OSプロセス起動コスト込み）"""
    # 1. .ndnファイルを書き換える
    with open(NDN_FILE, "w") as f:
        f.write(f'interest "{interest_name}"')
    
    # 2. コマンドを実行して時間を測る
    start = time.perf_counter()
    subprocess.run(["ndnc", "run", NDN_FILE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.perf_counter()
    
    duration = end - start
    print(f"[{label}]")
    print(f"  Target : {interest_name}")
    print(f"  Time   : {duration:.4f} sec")
    print("-" * 30)

def measure_dns_http():
    """HTTP通信を計測する"""
    target_host = "google.com"
    target_url = f"http://{target_host}"

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(target_url) as f:
            f.read(10) # データの一部を読む
    except Exception as e:
        print(f"HTTP Error: {e}")
    end = time.perf_counter()
    print(f"[HTTP Full]")
    print(f"  Target : {target_url} (Fetch Data)")
    print(f"  Time   : {(end - start):.4f} sec")
    print("-" * 30)

if __name__ == "__main__":
    print("=== Performance Benchmark: NDN vs HTTP ===\n")
    
    # NDNの計測
    measure_ndnc("NDN Local (Cache Hit)", "/data/ryu-local/")
    measure_ndnc("NDN Remote (Container)", "/data/ryu/")
    
    # DNS/HTTPの計測
    measure_dns_http()