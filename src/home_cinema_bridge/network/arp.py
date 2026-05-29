import ipaddress
import logging
from pathlib import Path


ARP_TABLE_PATH = Path("/proc/net/arp")


def find_mac_by_ip(ip_address: str) -> str | None:
    """
    Resolve a MAC address from the local ARP table.

    This works on Linux hosts/containers with access to /proc/net/arp.
    It requires the target device to have been seen recently by the host,
    so callers should try to contact/ping the device before using this.
    """
    try:
        normalized_ip = ipaddress.ip_address(ip_address).compressed
    except ValueError:
        logging.warning("Invalid IP address for ARP lookup: %s", ip_address)
        return None

    if not ARP_TABLE_PATH.exists():
        logging.debug("ARP table not available at %s", ARP_TABLE_PATH)
        return None

    try:
        lines = ARP_TABLE_PATH.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logging.warning("Unable to read ARP table: %s", exc)
        return None

    for line in lines[1:]:
        columns = line.split()
        if len(columns) < 4:
            continue

        ip, _, _, mac = columns[:4]

        if ip == normalized_ip and mac != "00:00:00:00:00:00":
            return mac.lower()

    return None