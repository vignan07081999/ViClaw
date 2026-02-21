import socket
import concurrent.futures

COMMON_PORTS = {
    8123: "Home Assistant",
    8006: "Proxmox VE",
    22: "SSH Service",
    80: "HTTP Server",
    443: "HTTPS Server",
    5000: "Flask/Local Web Server",
    8080: "Generic Web Control",
    631: "CUPS Printer",
    3000: "Node.js Server",
    8501: "Streamlit / ViClaw Dashboard"
}

def scan_port(ip, port, timeout=0.1):
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
            return (ip, services)
        return None

    # parallelize the sweep
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(_scan_host, hosts_to_scan)
        
    for res in results:
        if res:
            discovered[res[0]] = res[1]
            
    return discovered
