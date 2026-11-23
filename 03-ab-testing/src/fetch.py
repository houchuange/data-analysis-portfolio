# -*- coding: utf-8 -*-
"""
fetch.py — 数据获取与完整性校验
项目：Cookie Cats 新手引导门槛 A/B 实验评估
数据源：Tactile Entertainment / DataCamp 公开实验数据（经 GitHub 镜像分发）
说明：数据集公开但无官方托管地址，因此固定镜像 + SHA-256 校验，保证任何人复现到的是同一份数据。
"""
import hashlib
import os
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)
OUT = os.path.join(DATA_DIR, "cookie_cats.csv")

# 主镜像与备用镜像（内容一致，SHA-256 相同）
MIRRORS = [
    "https://raw.githubusercontent.com/0zz10/CookieCats-AB-Testing/master/datasets/cookie_cats.csv",
    "https://cdn.jsdelivr.net/gh/0zz10/CookieCats-AB-Testing@master/datasets/cookie_cats.csv",
]
EXPECTED_SHA256 = "5ab54d761fbddcd50de7b88e4eaf7837cba4569474f50c043a4d17ee342c46bd"


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: str, retries: int = 3) -> None:
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                payload = r.read()
            if len(payload) < 1_000_000:
                raise ValueError(f"响应过小（{len(payload)} bytes），疑似错误页")
            with open(dest, "wb") as f:
                f.write(payload)
            return
        except Exception as e:  # noqa: BLE001
            print(f"  第 {attempt} 次失败：{e}")
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def main() -> None:
    if os.path.exists(OUT) and sha256_of(OUT) == EXPECTED_SHA256:
        print(f"[skip] 本地文件已存在且校验通过：{OUT}")
    else:
        for url in MIRRORS:
            print(f"[get ] {url}")
            try:
                download(url, OUT)
            except Exception as e:  # noqa: BLE001
                print(f"  镜像不可用：{e}")
                continue
            if sha256_of(OUT) == EXPECTED_SHA256:
                break
            print("  校验不通过，尝试下一个镜像")

    actual = sha256_of(OUT)
    if actual != EXPECTED_SHA256:
        raise SystemExit(f"数据校验失败\n  期望 {EXPECTED_SHA256}\n  实际 {actual}")

    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f"[ok  ] SHA-256 校验通过（{size_mb:.2f} MB）")
    print(f"[ok  ] {OUT}")


if __name__ == "__main__":
    main()
