# -*- coding: utf-8 -*-
"""
dns_override.py —— 纯 Python 公共 DNS 解析补丁
=================================================
本机 DNS（路由器 192.168.2.1）间歇性超时，导致所有外网域名解析失败。
此模块绕过系统解析器，直接向公共 DNS（阿里/腾讯/114/Google）发 UDP 查询，
解析 A 记录（自动跟随 CNAME 链），并 patch socket.getaddrinfo，使
requests/urllib3 等库自动使用公共 DNS，无需管理员权限、无需改系统配置。
"""
import socket
import struct
import random
import threading
import time

SERVERS = [
    ("223.5.5.5", 53),     # 阿里 AliDNS
    ("119.29.29.29", 53),  # 腾讯 DNSPod
    ("114.114.114.114", 53),  # 114DNS
    ("8.8.8.8", 53),       # Google
]
TIMEOUT = 3.0
CACHE_TTL = 300
_patched = False
_cache = {}
_lock = threading.Lock()


def _build_query(qid, name):
    parts = []
    for label in name.split("."):
        b = label.encode("ascii")
        parts.append(bytes([len(b)]) + b)
    parts.append(b"\x00")
    qname = b"".join(parts)
    return struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + qname + struct.pack(">HH", 1, 1)


def _parse_name(msg, off):
    labels = []
    jumped = False
    orig = off
    while True:
        if off >= len(msg):
            raise ValueError("name out of range")
        ln = msg[off]
        if ln == 0:
            off += 1
            break
        if ln & 0xC0 == 0xC0:
            ptr = struct.unpack(">H", msg[off:off + 2])[0] & 0x3FFF
            if not jumped:
                orig = off + 2
                jumped = True
            off = ptr
            continue
        off += 1
        labels.append(msg[off:off + ln].decode("ascii", "replace"))
        off += ln
    return ".".join(labels), (orig if jumped else off)


def _query_once(server, qname):
    qid = random.randint(0, 0xFFFF)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    try:
        sock.sendto(_build_query(qid, qname), server)
        data, _ = sock.recvfrom(4096)
    finally:
        sock.close()
    if len(data) < 12:
        raise ValueError("short response")
    rid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    if rid != qid:
        raise ValueError("mismatched id")
    if flags & 0x8000 == 0:
        raise ValueError("not a response")
    rcode = flags & 0x000F
    if rcode != 0:
        raise ValueError(f"rcode={rcode}")
    off = 12
    for _ in range(qd):
        _, off = _parse_name(data, off)
        off += 4
    addrs = []
    cnames = []
    for _ in range(an):
        _, off = _parse_name(data, off)
        rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[off:off + 10])
        off += 10
        rdata = data[off:off + rdlen]
        off += rdlen
        if rtype == 1 and rdlen == 4:
            addrs.append(socket.inet_ntoa(rdata))
        elif rtype == 5:
            target, _ = _parse_name(data, off - rdlen)
            cnames.append(target)
    return addrs, cnames


def resolve(name):
    """返回 A 记录 IP 列表，自动跟随 CNAME 链。"""
    now = time.time()
    with _lock:
        hit = _cache.get(name)
        if hit and hit[0] > now:
            return hit[1]
    qname = name.rstrip(".")
    seen = set()
    for _ in range(8):
        if qname in seen:
            break
        seen.add(qname)
        last_err = None
        for server in SERVERS:
            try:
                addrs, cnames = _query_once(server, qname)
                if addrs:
                    with _lock:
                        _cache[name] = (now + CACHE_TTL, addrs)
                    return addrs
                if cnames:
                    qname = cnames[0].rstrip(".")
                    break
            except Exception as e:
                last_err = e
        else:
            if last_err is not None:
                break
    return []


_orig_getaddrinfo = socket.getaddrinfo


def _getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if isinstance(host, str):
        h = host.strip().strip("[]")
        is_ip = False
        try:
            socket.inet_pton(socket.AF_INET, h)
            is_ip = True
        except OSError:
            try:
                socket.inet_pton(socket.AF_INET6, h)
                is_ip = True
            except OSError:
                pass
        if not is_ip and ("." in h):
            addrs = resolve(h)
            if addrs:
                af = family if family in (0, socket.AF_INET) else socket.AF_INET
                results = []
                for a in addrs:
                    socktype = type if type else socket.SOCK_STREAM
                    proto_ = proto if proto else (socket.IPPROTO_TCP if socktype == socket.SOCK_STREAM else socket.IPPROTO_UDP)
                    results.append((socket.AF_INET, socktype, proto_, "", (a, port)))
                return results
    return _orig_getaddrinfo(host, port, family, type, proto, flags)


def patch():
    global _patched
    if not _patched:
        socket.getaddrinfo = _getaddrinfo
        _patched = True


if __name__ == "__main__":
    import sys
    patch()
    for host in sys.argv[1:] or ["api.xiaomimimo.com", "tokenhub.tencentmaas.com", "www.baidu.com"]:
        print(host, "->", resolve(host))
