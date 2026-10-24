import ipaddress
import socket
from urllib.parse import urlparse
from typing import Tuple, Optional


BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        for net in BLOCKED_NETWORKS:
            if ip in net:
                return True
        return False
    except ValueError:
        return True


def validate_url_security(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    if not url:
        return False, None, "URL cannot be empty."

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ["http", "https"]:
        return False, None, f"Scheme '{parsed.scheme}' is not permitted. Only HTTP/HTTPS allowed."

    if parsed.username or parsed.password:
        return False, None, "URLs with embedded user credentials are not permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, None, "URL does not have a valid hostname."

    if hostname.lower() in ["localhost", "127.0.0.1", "::1", "docker-host"]:
        return False, None, "Access to localhost or local loopback is prohibited."

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        if not addr_info:
            return False, None, f"Could not resolve host: {hostname}"

        resolved_ips = set()
        for item in addr_info:
            sockaddr = item[4]
            ip_str = sockaddr[0]
            resolved_ips.add(ip_str)

        for ip in resolved_ips:
            if is_ip_blocked(ip):
                return False, ip, f"Hostname resolves to restricted address: {ip}"

        first_ip = next(iter(resolved_ips))
        return True, first_ip, None
    except socket.gaierror:
        return False, None, f"DNS resolution failed for hostname: {hostname}"
    except Exception as exc:
        return False, None, f"URL security validation error: {str(exc)}"
