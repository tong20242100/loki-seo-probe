#!/usr/bin/env python3
"""fetch() 重试门禁：502 / 网络错须重试，穷尽 RETRIES 次后返回 status=0 且 error 标记。

只 patch urllib.request.urlopen（被调的下一层），让 fetch 保持真实执行——
不能 patch fetch 自身（那会把重试分支整段跳过，门禁形同虚设）。
"""
import importlib.util
import sys
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location("au", "scripts/audit_url.py")
au = importlib.util.module_from_spec(spec)
spec.loader.exec_module(au)

CALLS = {"n": 0}


class _Resp:
    def __init__(self, status, body=b""):
        self.status = status
        self._b = body
        self.headers = {}
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def geturl(self): return "http://x/"
    def read(self, n=0): return self._b


def make_fake(kind, succeed_on):
    def fake(req, timeout=None, context=None):
        CALLS["n"] += 1
        if CALLS["n"] < succeed_on:
            if kind == "http":
                raise HTTPError("http://x/", 502, "B", {}, None)
            raise URLError("Tunnel 502")
        return _Resp(200, b"<html>")
    return fake


def run_case(label, kind, succeed_on, expect_status, expect_calls):
    CALLS["n"] = 0
    au.urlopen = make_fake(kind, succeed_on)
    r = au.fetch("http://x/")
    ok = (r["status"] == expect_status and CALLS["n"] == expect_calls)
    if not ok:
        print(f"[FAIL] {label}: status={r['status']} calls={CALLS['n']} "
              f"(want {expect_status}/{expect_calls})")
    return ok


def main():
    results = [
        run_case("HTTP502 retry->200", "http", 3, 200, 3),
        run_case("URLError retry->200", "url", 2, 200, 2),
        # 站点真 502（最后一次仍是 HTTP 502）：如实报 502，不被重试掩盖成 0
        run_case("HTTP502 穷尽->仍502(真实站点错)", "http", 99, 502, 3),
        # 代理抖动（最后一次仍是 URLError）：探针失败 status=0（上游按 na 处理）
        run_case("URLError 穷尽-> status0(探针失败)", "url", 99, 0, 3),
    ]
    if all(results):
        print("fetch 重试门禁: 全部通过")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
