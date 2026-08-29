"""Find the label printer on the LAN.

The printer gets its address from DHCP, so a hardcoded IP is a slow-motion
outage: the lease changes, prints silently queue forever, and nobody notices
until they go looking for a label. This resolves the address at print time
instead, in cheapest-first order:

    1. the last address that worked (cached on disk, survives restarts)
    2. PRINTER_HOST, if configured (an mDNS name like BRW3C2AF4.local)
    3. an mDNS browse for printers advertising port 9100
    4. a sweep of the local subnet for anything listening on 9100

Everything is probed with a real TCP connect before being trusted, so a stale
cache entry costs one short timeout rather than a failed print. A successful
lookup is written back to the cache.

The sweep exists because mDNS is not reliable here: this Pi sits behind a
Starlink router that does not forward multicast between wireless clients, so
neither avahi nor zeroconf sees a single service on the LAN even though the
Pi is correctly joined to 224.0.0.251. mDNS is kept ahead of it anyway — it is
cheap, and it starts working the day the network does.

Returning None is a normal outcome, not an error: the printer is simply off.
The caller should treat it as "retry later", never as a failed job.
"""
from __future__ import annotations
import ipaddress
import logging
import os
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

log = logging.getLogger("tundra-print.discover")

# Brother advertises port 9100 under this type; _printer._tcp is LPD (515) but
# the same host usually answers on 9100 too, so it is a useful fallback hint.
SERVICE_TYPES = ["_pdl-datastream._tcp.local.", "_printer._tcp.local."]

PROBE_TIMEOUT = 1.5     # seconds for a single TCP connect test
MDNS_TIMEOUT = 4.0      # seconds to listen for mDNS answers
SWEEP_TIMEOUT = 0.4     # per-host connect timeout during a subnet sweep
SWEEP_WORKERS = 64
SWEEP_MAX_HOSTS = 1024  # refuse to sweep anything bigger than a /22


def _probe(host: str, port: int, timeout: float = PROBE_TIMEOUT) -> bool:
    """True if something accepts a TCP connection there."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _read_cache(path: Path) -> str | None:
    try:
        value = path.read_text().strip()
        return value or None
    except OSError:
        return None


def _write_cache(path: Path, value: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n")
    except OSError as e:
        # A read-only state dir shouldn't break printing, just make it slower.
        log.warning("could not cache printer address in %s: %s", path, e)


def _mdns_services(timeout: float = MDNS_TIMEOUT) -> list:
    """Browse mDNS for printers. Returns zeroconf ServiceInfo objects."""
    try:
        from zeroconf import Zeroconf, ServiceBrowser
    except ImportError:
        log.warning("zeroconf not installed; skipping mDNS discovery")
        return []

    found: list = []

    class _Listener:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name, timeout=2000)
            if info is not None:
                found.append(info)

        def update_service(self, zc, type_, name):
            pass

        def remove_service(self, zc, type_, name):
            pass

    zc = Zeroconf()
    try:
        listener = _Listener()
        for service_type in SERVICE_TYPES:
            ServiceBrowser(zc, service_type, listener)
        time.sleep(timeout)
    except Exception as e:  # noqa: BLE001 — discovery is best-effort
        log.warning("mDNS browse failed: %s", e)
    finally:
        try:
            zc.close()
        except Exception:  # noqa: BLE001
            pass
    return found


def _looks_like(info, model: str) -> bool:
    """Does this advertised service look like the printer we want?"""
    needle = model.lower().replace("-", "")
    haystack = [info.name.lower()]
    for key, value in (info.properties or {}).items():
        for raw in (key, value):
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "replace")
            if isinstance(raw, str):
                haystack.append(raw.lower())
    return any(needle in h.replace("-", "") for h in haystack)


def _local_networks() -> list[ipaddress.IPv4Network]:
    """Directly-attached IPv4 subnets, read from the kernel routing table.

    /proc/net/route avoids both a subprocess and an extra dependency. Fields
    are little-endian hex, and a destination of 0 is the default route, which
    is not a subnet we can sweep.
    """
    nets: list[ipaddress.IPv4Network] = []
    try:
        with open("/proc/net/route") as f:
            next(f)  # header
            for line in f:
                parts = line.split()
                if len(parts) < 8:
                    continue
                iface, dest_hex, _gw, flags_hex = parts[0], parts[1], parts[2], parts[3]
                mask_hex = parts[7]
                if iface == "lo":
                    continue
                if int(flags_hex, 16) & 0x2:  # RTF_GATEWAY — not directly attached
                    continue
                dest = struct.unpack("<I", bytes.fromhex(dest_hex))[0]
                mask = struct.unpack("<I", bytes.fromhex(mask_hex))[0]
                if dest == 0 or mask == 0:
                    continue
                try:
                    net = ipaddress.IPv4Network(
                        f"{ipaddress.IPv4Address(dest)}/{ipaddress.IPv4Address(mask)}"
                    )
                except ValueError:
                    continue
                if net.num_addresses <= SWEEP_MAX_HOSTS and net not in nets:
                    nets.append(net)
    except OSError as e:
        log.warning("could not read routing table: %s", e)
    return nets


def _sweep(port: int, prefer_near: str | None = None) -> str | None:
    """Look for anything listening on `port` across the local subnets.

    This is the fallback that actually works on a network without mDNS. Very
    little else listens on 9100, so a hit is almost certainly the printer —
    and it is probed the same way as every other candidate.
    """
    nets = _local_networks()
    if not nets:
        return None

    # Search the subnet the printer was last seen on first.
    if prefer_near:
        try:
            near = ipaddress.IPv4Address(prefer_near)
            nets.sort(key=lambda n: near not in n)
        except ValueError:
            pass

    for net in nets:
        hosts = [str(h) for h in net.hosts()]
        log.info("sweeping %s for :%s (%d hosts)", net, port, len(hosts))
        with ThreadPoolExecutor(max_workers=SWEEP_WORKERS) as pool:
            results = pool.map(lambda h: (h, _probe(h, port, SWEEP_TIMEOUT)), hosts)
            for host, ok in results:
                if ok:
                    log.info("found something on %s:%s", host, port)
                    return host
    return None


def find_printer(
    *,
    model: str,
    port: int = 9100,
    seed_host: str | None = None,
    mdns_host: str | None = None,
    cache_path: Path | None = None,
) -> str | None:
    """Return a reachable "host:port" for the printer, or None if it's offline.

    `seed_host` is the configured last-known address, `mdns_host` an explicit
    hostname to try (PRINTER_HOST).
    """
    tried: list[str] = []

    # 1. Whatever worked last time, then the configured address. Both are just
    #    hints — each is probed before use.
    cached = _read_cache(cache_path) if cache_path else None
    for host in (cached, seed_host):
        if host and host not in tried:
            tried.append(host)
            if _probe(host, port):
                log.info("printer at %s:%s (known address)", host, port)
                return f"{host}:{port}"

    # 2. An explicit hostname. Works through avahi via normal name resolution.
    if mdns_host and mdns_host not in tried:
        tried.append(mdns_host)
        try:
            addr = socket.gethostbyname(mdns_host)
        except OSError:
            addr = None
        if addr and _probe(addr, port):
            log.info("printer at %s:%s (resolved %s)", addr, port, mdns_host)
            if cache_path:
                _write_cache(cache_path, addr)
            return f"{addr}:{port}"

    # 3. Ask the network who is out there. Prefer a model match; if there is
    #    exactly one printer advertising, take it.
    services = _mdns_services()
    if services:
        matches = [s for s in services if _looks_like(s, model)]
        candidates = matches or (services if len(services) == 1 else [])
        for info in candidates:
            for addr in info.parsed_addresses():
                if ":" in addr:  # skip IPv6; brother_ql speaks v4
                    continue
                if _probe(addr, port):
                    how = "model match" if matches else "only printer on the network"
                    log.info("printer at %s:%s (mDNS, %s: %s)", addr, port, how, info.name)
                    if cache_path:
                        _write_cache(cache_path, addr)
                    return f"{addr}:{port}"
        log.warning(
            "mDNS saw %d printer service(s) but none answered on :%s", len(services), port
        )

    # 4. Nothing announced itself. Go look.
    if os.environ.get("PRINTER_SWEEP", "1") != "0":
        host = _sweep(port, prefer_near=cached or seed_host)
        if host:
            if cache_path:
                _write_cache(cache_path, host)
            return f"{host}:{port}"

    log.info("printer not found (tried %s, then mDNS, then a subnet sweep) "
             "— it is probably off", ", ".join(tried) or "nothing cached")
    return None


def cache_path_from_env() -> Path:
    """Where to remember the printer's address between runs."""
    explicit = os.environ.get("PRINTER_CACHE_FILE")
    if explicit:
        return Path(explicit)
    # systemd sets STATE_DIRECTORY from StateDirectory= in the unit.
    state = os.environ.get("STATE_DIRECTORY")
    if state:
        return Path(state.split(":")[0]) / "printer-address"
    return Path("/var/lib/tundra-print/printer-address")
