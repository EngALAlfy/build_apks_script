"""Publish a stable .local name on the LAN and follow interface/IP changes."""
import ipaddress
import re
import socket
import threading

import ifaddr
from zeroconf import IPVersion, ServiceInfo, Zeroconf

SERVICE_TYPE = '_http._tcp.local.'
VIRTUAL_NAMES = ('virtual', 'vethernet', 'hyper-v', 'loopback', 'docker', 'wsl', 'vpn', 'vmware', 'vbox', 'tailscale', 'wireguard', 'tunnel', 'tap-')


def normalize_name(value):
    label = value.strip().lower().rstrip('.')
    if label.endswith('.local'):
        label = label[:-6]
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label):
        raise ValueError('LAN name must be one DNS label of 1–63 letters, digits, or hyphens, optionally followed by .local.')
    return label + '.local.'


def usable_ipv4(value):
    if not isinstance(value, str):
        return False
    try:
        ip = ipaddress.ip_address(value)
        return ip.version == 4 and not (ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast)
    except ValueError:
        return False


def preferred_address():
    # UDP connect selects the routing interface without sending any packet.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
            route.connect(('192.0.2.1', 9))
            return route.getsockname()[0]
    except OSError:
        return None


def discover_addresses(interface=None, bind_address='0.0.0.0'):
    if bind_address not in ('0.0.0.0', '::'):
        return [bind_address] if usable_ipv4(bind_address) else []
    candidates, physical = set(), set()
    for adapter in ifaddr.get_adapters():
        names = (str(adapter.name).casefold(), adapter.nice_name.casefold(), str(adapter.index))
        if interface and interface.casefold() not in names:
            continue
        addresses = {ip.ip for ip in adapter.ips if usable_ipv4(ip.ip)}
        candidates.update(addresses)
        if not any(word in ' '.join(names) for word in VIRTUAL_NAMES):
            physical.update(addresses)
    if interface:
        return sorted(candidates)
    # Do not publish Hyper-V/WSL/VPN addresses to ordinary LAN clients.
    eligible = physical
    preferred = preferred_address()
    return [preferred] if preferred in eligible else sorted(eligible)


class Discovery:
    def __init__(self, name='apk-builder', port=8080, interface=None, bind_address='0.0.0.0', enabled=True, interval=15):
        self.hostname = normalize_name(name)
        self.port, self.interface, self.bind_address = port, interface, bind_address
        self.enabled, self.interval = enabled, interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._state = 'starting' if enabled else 'disabled'
        self._addresses, self._error = [], None
        self._zc, self._info, self._thread = None, None, None
        self._registered = False

    def status(self):
        with self._lock:
            return dict(hostname=self.hostname.rstrip('.'), url=f'http://{self.hostname.rstrip(".")}:{self.port}',
                        hostname_url=f'http://{socket.gethostname().lower()}:{self.port}',
                        status=self._state, addresses=list(self._addresses), error=self._error)

    def _set_state(self, state, addresses=(), error=None):
        with self._lock:
            changed = state != self._state or list(addresses) != self._addresses
            self._state, self._addresses, self._error = state, list(addresses), error
        if changed:
            if state == 'advertised':
                print(f'LAN name active: http://{self.hostname.rstrip(".")}:{self.port} ({", ".join(addresses)})', flush=True)
            elif state == 'unavailable':
                print(f'LAN name discovery unavailable ({error}); HTTP/IP access remains available. Retrying.', flush=True)

    def start(self):
        if self.enabled and not self._thread:
            self._thread = threading.Thread(target=self._run, name='lan-name-discovery', daemon=True)
            self._thread.start()

    def _close(self):
        if self._zc:
            try:
                if self._info and self._registered:
                    self._zc.unregister_service(self._info)
            finally:
                self._zc.close()
                self._zc, self._info = None, None
                self._registered = False

    def refresh(self):
        addresses = discover_addresses(self.interface, self.bind_address)
        if not addresses:
            self._close()
            self._set_state('unavailable', error='No usable IPv4 LAN interface')
            return
        if self._zc and addresses == self._addresses:
            return
        self._close()
        self._zc = Zeroconf(interfaces=addresses, ip_version=IPVersion.V4Only)
        label = self.hostname[:-7]
        self._info = ServiceInfo(SERVICE_TYPE, label + '.' + SERVICE_TYPE,
                                 addresses=[socket.inet_aton(address) for address in addresses], port=self.port,
                                 properties={'path': '/', 'title': 'APK Builder'}, server=self.hostname,
                                 host_ttl=30, other_ttl=60)
        # Keep the requested name; do not silently change the shareable URL.
        self._zc.register_service(self._info, allow_name_change=False)
        self._registered = True
        self._set_state('advertised', addresses)

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    self.refresh()
                except Exception as exc:
                    try:
                        self._close()
                    except Exception:
                        pass
                    self._set_state('unavailable', error=type(exc).__name__)
                self._stop.wait(self.interval)
        finally:
            self._close()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        else:
            self._close()
