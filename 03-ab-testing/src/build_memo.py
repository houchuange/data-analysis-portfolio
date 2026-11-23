# -*- coding: utf-8 -*-
"""
build_memo.py — 把 memo/readout.html 打成 PDF

用 Chrome 的 headless 模式打印，A4、无页眉页脚。
Chrome 直接往项目目录写会被系统拦（拒绝访问 0x5），所以先输出到临时目录再拷回来。
"""
import os
import shutil
import subprocess
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "memo", "readout.html")
OUT = os.path.join(BASE, "memo", "cookie-cats-gate-readout.pdf")

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome():
    for p in CHROME:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("没找到 chrome.exe，改一下 CHROME 里的路径")


def main():
    chrome = find_chrome()
    tmp = os.path.join(tempfile.gettempdir(), "cc_readout.pdf")
    if os.path.exists(tmp):
        os.remove(tmp)

    subprocess.run([
        chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        "--virtual-time-budget=4000",
        f"--print-to-pdf={tmp}",
        "file:///" + SRC.replace("\\", "/"),
    ], check=True, capture_output=True)

    shutil.copyfile(tmp, OUT)
    print(f"→ {OUT}  ({os.path.getsize(OUT) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
