# Stable LAN address

Use **http://apk-builder.local:8080** to reach the central build server on the same local network. The hostname stays the same when the PC receives a different LAN IP. No static IP assignment, Windows computer rename, or per-client hosts-file edit is required for mDNS-capable clients.

## How the name works

The server publishes `apk-builder.local` through multicast DNS and advertises its HTTP service. It selects an active physical IPv4 interface, avoiding typical VPN, Hyper-V, and WSL interfaces. A background check every 15 seconds republishes the same hostname when the selected address changes. Address records have a 30-second advertised TTL; clients may briefly cache an old address during a network change.

Name discovery starts with the server and stops with it. It also starts through the existing hidden Windows sign-in task. Browser launch stays disabled in automatic startup. The **Server environment** panel shows the active name, and administrator **Server settings** shows a shareable address field.

The existing Windows computer name is a separate fallback, currently `http://desktop-44dpm7b:8080`. Resolution of that computer name depends on the client's network naming support. `http://localhost:8080` always refers to the PC on which the browser is running; use it on the server PC for first-administrator setup.

## Requirements and limitations

Multicast DNS uses `.local` names on the local network link and UDP port 5353. Clients must support mDNS, and the network must allow local multicast. It does not automatically cross guest Wi-Fi isolation, VLANs, routers, or VPNs. The HTTP listener remains on TCP port 8080.

If a device cannot resolve the name, check whether it is on the same LAN, whether guest/client isolation is enabled, and whether multicast or UDP 5353 is blocked. The app does not change firewall, router, DNS-server, or operating-system network settings. Successful registration means the server is advertising; it does not prove every other device can receive the announcements.

For environments that block mDNS or need a name across subnets, configure a hostname in the network's DNS/router instead. For example, a router-managed `apk-builder.home.arpa` record can point to a DHCP reservation or dynamically updated host entry. That requires router/DNS administration. Editing a hosts file on only the server PC does not configure name resolution for other devices.

See the [Multicast DNS specification](https://www.rfc-editor.org/rfc/rfc6762) and the [python-zeroconf registration example](https://github.com/python-zeroconf/python-zeroconf/blob/master/examples/registration.py) for the protocol and library used.

## Choose another name

For a manual source launch:

```powershell
python server_main.py --lan-name release-builder
```

The address becomes `http://release-builder.local:8080`. A name must be a single label containing 1–63 letters, digits, or hyphens, with no leading/trailing hyphen. Names ending in `.local` are accepted too. Use a unique name on the LAN; service-name conflicts are reported rather than silently renaming the URL.

For automatic sign-in startup:

```powershell
.\scripts\install-startup.ps1 -StartupMode Logon -LanName release-builder -StartNow
```

Changing a running supervisor's registered arguments does not replace that running instance. Restart the managed task during a maintenance window, or let the new arguments take effect at the next sign-in. Keep the current server running while builds are active.

## Select an interface or disable discovery

Automatic selection uses a physical adapter and prefers the normal routing interface. To override it, use an adapter description, GUID, or index:

```powershell
python server_main.py --lan-interface 3
.\scripts\install-startup.ps1 -StartupMode Logon -LanInterface 3
```

Virtual interfaces are excluded automatically, but an explicitly selected adapter is allowed. Interface selection is based on the adapter, so an address change on that adapter does not require changing the hostname.

To disable announcements:

```powershell
python server_main.py --no-mdns
.\scripts\install-startup.ps1 -StartupMode Logon -NoMdns
```

Loopback-only listeners disable mDNS automatically. Discovery failure does not stop the HTTP server; numeric-IP access and existing computer-name resolution remain available.

## Authentication

This changes the address, not the access controls. All dashboard accounts, roles, project permissions, queue entries, and artifacts remain unchanged. Cookies are scoped by browser hostname, so a browser moving from a numeric IP or localhost to `apk-builder.local` may ask you to sign in again. Initial administrator creation is still restricted to the server PC's loopback URL.

This alias uses the existing HTTP port; it does not add HTTPS. If you run an HTTPS reverse proxy, use its configured DNS name and TLS configuration instead.
