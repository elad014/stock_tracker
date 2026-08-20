import ipaddress
import re
import socket
from urllib.parse import urlparse

_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
    }
)
_BLOCKED_HOSTNAME_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home")


def clean_text(value: str) -> str:
    text = _WHITESPACE_RE.sub(" ", value)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def _host_resolves_to_blocked_ip(hostname: str) -> bool:
    lowered = hostname.lower().rstrip(".")
    if lowered in _BLOCKED_HOSTNAMES:
        return True
    if any(lowered.endswith(suffix) for suffix in _BLOCKED_HOSTNAME_SUFFIXES):
        return True
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        return _ip_is_blocked(literal)
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return True
    if not infos:
        return True
    for info in infos:
        try:
            resolved = ipaddress.ip_address(str(info[4][0]))
        except ValueError:
            return True
        if _ip_is_blocked(resolved):
            return True
    return False


def is_safe_article_url(url: str) -> bool:
    """True only for http(s) URLs whose host resolves to a public internet address."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    return not _host_resolves_to_blocked_ip(hostname)
