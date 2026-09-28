"""IP address classification helpers for SSRF protection.

Uses Python's ``ipaddress`` standard library for canonical parsing.
No regex-based IP matching — only proper address objects.
"""

import ipaddress
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network

# ---------------------------------------------------------------------------
# Blocked IPv4 ranges (not publicly routable)
# ---------------------------------------------------------------------------

_BLOCKED_IPV4_NETWORKS: list[IPv4Network] = [
    IPv4Network("127.0.0.0/8"),      # Loopback (RFC 5735)
    IPv4Network("10.0.0.0/8"),       # Private (RFC 1918)
    IPv4Network("172.16.0.0/12"),    # Private (RFC 1918)
    IPv4Network("192.168.0.0/16"),   # Private (RFC 1918)
    IPv4Network("169.254.0.0/16"),   # Link-local / AWS metadata (RFC 3927)
    IPv4Network("100.64.0.0/10"),    # Shared address space / CGNAT (RFC 6598)
    IPv4Network("0.0.0.0/8"),        # "This" network (RFC 1122)
    IPv4Network("224.0.0.0/4"),      # Multicast (RFC 5771)
    IPv4Network("240.0.0.0/4"),      # Reserved (RFC 1112)
    IPv4Network("192.0.2.0/24"),     # TEST-NET-1 (RFC 5737)
    IPv4Network("198.51.100.0/24"),  # TEST-NET-2 (RFC 5737)
    IPv4Network("203.0.113.0/24"),   # TEST-NET-3 (RFC 5737)
    IPv4Network("192.0.0.0/24"),     # IETF Protocol Assignments
    IPv4Network("198.18.0.0/15"),    # Benchmarking (RFC 2544)
    IPv4Network("192.88.99.0/24"),   # 6to4 relay anycast, deprecated (RFC 7526)
]

# ---------------------------------------------------------------------------
# Blocked IPv6 ranges (not publicly routable)
# ---------------------------------------------------------------------------

_BLOCKED_IPV6_NETWORKS: list[IPv6Network] = [
    IPv6Network("::1/128"),          # Loopback (RFC 4291)
    IPv6Network("fc00::/7"),         # Unique local (RFC 4193)
    IPv6Network("fe80::/10"),        # Link-local (RFC 4291)
    IPv6Network("ff00::/8"),         # Multicast (RFC 4291)
    IPv6Network("::/128"),           # Unspecified (RFC 4291)
    IPv6Network("::ffff:0:0/96"),    # IPv4-mapped IPv6 (RFC 4291)
    IPv6Network("64:ff9b::/96"),     # IPv4/IPv6 translation (RFC 6052)
    IPv6Network("64:ff9b:1::/48"),   # IPv4/IPv6 translation (RFC 8215)
    IPv6Network("100::/64"),         # Discard (RFC 6666)
    IPv6Network("2001::/32"),        # Teredo (RFC 4380)
    IPv6Network("2001:db8::/32"),    # Documentation (RFC 3849)
    IPv6Network("2002::/16"),        # 6to4 (RFC 3056)
]


def is_public_ip(ip_str: str) -> bool:
    """Return True only if *ip_str* is a publicly routable address.

    Handles IPv4, IPv6, and IPv4-mapped IPv6 (``::ffff:x.x.x.x``).
    Returns False for any malformed or non-public address.
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if isinstance(addr, IPv4Address):
        return _is_public_ipv4(addr)

    if isinstance(addr, IPv6Address):
        # Unwrap IPv4-mapped addresses before checking
        if addr.ipv4_mapped is not None:
            return _is_public_ipv4(addr.ipv4_mapped)
        return _is_public_ipv6(addr)

    return False  # pragma: no cover


def _is_public_ipv4(addr: IPv4Address) -> bool:
    return all(addr not in net for net in _BLOCKED_IPV4_NETWORKS)


def _is_public_ipv6(addr: IPv6Address) -> bool:
    return all(addr not in net for net in _BLOCKED_IPV6_NETWORKS)
