import socket
import concurrent.futures

COMMON_PORTS = {
    8123: "Home Assistant",
    8006: "Proxmox VE",
    8989: "Sonarr",
    7878: "Radarr",
    8988: "Lidarr",
    8686: "Readarr",
    8787: "Whisparr",
    9696: "Prowlarr",
    8096: "Jellyfin/Emby",
    32400: "Plex Media Server",
    81: "Nginx Proxy Manager",
    9443: "Portainer/Nginx Proxy Manager",
    8080: "Generic Web Control/Traefik",
    9000: "Portainer (HTTP)",
    8443: "UniFi Network Controller",
    5000: "OctoPrint / Flask Server",
    7125: "Moonraker / Klipper",
    5055: "Overseerr / Jellyseerr",
    53: "Pi-hole / AdGuard Home (DNS)",
    8384: "Syncthing",
    3000: "Grafana",
    9090: "Prometheus",
    631: "CUPS Printer",
    5001: "Synology DiskStation",
    1883: "MQTT Broker",
    1880: "Node-RED",
    8920: "Emby (HTTPS)",
    19999: "Netdata",
    5080: "Frigate NVR",
    8581: "Homebridge",
    8200: "Duplicati",
    8090: "qBittorrent",
    6881: "Transmission / Deluge",
    1194: "OpenVPN",
    51820: "WireGuard",
    8000: "Docker App (Generic)",
    8008: "Scrypted",
    8501: "Streamlit / ViClaw Dashboard"
}

def scan_port(ip, port, timeout=1.0):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def discover_local_subnet():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        ip_parts = local_ip.split(".")
        return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}."
    except Exception:
        return "192.168.1."

def quick_scan():
    """Returns a dictionary of discovered IPs to their identified services."""
    subnet = discover_local_subnet()
    discovered = {}
    
    # We only scan ports that indicate something we can integrate with
    target_ports = list(COMMON_PORTS.keys())
    hosts_to_scan = [f"{subnet}{i}" for i in range(1, 255)]
    
    def _scan_host(ip):
        services = []
        for port in target_ports:
            if scan_port(ip, port):
                services.append(COMMON_PORTS[port])
        if services:
            hostname = ip
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except Exception:
                pass
            return (ip, hostname, services)
        return None

    # parallelize the sweep
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(_scan_host, hosts_to_scan)
        
    for res in results:
        if res:
            discovered[res[0]] = {"hostname": res[1], "services": res[2]}
            
    return discovered
