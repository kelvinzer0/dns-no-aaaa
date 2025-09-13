import socket
import threading
import os
import sys
from dnslib import DNSRecord, DNSHeader, QTYPE

class SimpleDNSFilter:
    def __init__(self, upstream_dns=None):
        self.upstream_dns = upstream_dns or os.getenv('UPSTREAM_DNS', '8.8.8.8')
        print(f"Using upstream DNS: {self.upstream_dns}")
    
    def handle_dns_request(self, data):
        try:
            request = DNSRecord.parse(data)
            
            # Check for AAAA queries
            for question in request.questions:
                if question.qtype == QTYPE.AAAA:
                    print(f"🚫 Blocked AAAA: {question.qname}")
                    # Return empty response for AAAA
                    response = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), 
                                       q=question)
                    return response.pack()
            
            # Forward other queries to upstream DNS
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(5)
                sock.sendto(data, (self.upstream_dns, 53))
                response_data, _ = sock.recvfrom(1024)
            
            return response_data
            
        except Exception as e:
            print(f"Error handling DNS request: {e}")
            return data

def create_udp_socket():
    """Create UDP socket with fallback from port 53 to 5353"""
    ports_to_try = [53, 5353, 5354, 5355]
    
    for port in ports_to_try:
        try:
            # Try IPv6 socket (supports both IPv4 and IPv6)
            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            sock.bind(('::', port))
            print(f"✅ UDP successfully bound to port {port}")
            return sock, port
        except OSError as e:
            print(f"❌ Cannot bind UDP to port {port}: {e}")
            if port == ports_to_try[-1]:
                raise Exception(f"Failed to bind UDP to any port: {ports_to_try}")
            print(f"🔄 Trying next port: {ports_to_try[ports_to_try.index(port) + 1]}")
    
    raise Exception("No UDP ports available")

def create_tcp_socket():
    """Create TCP socket with fallback from port 53 to 5353"""
    ports_to_try = [53, 5353, 5354, 5355]
    
    for port in ports_to_try:
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.bind(('::', port))
            sock.listen(5)
            print(f"✅ TCP successfully bound to port {port}")
            return sock, port
        except OSError as e:
            print(f"❌ Cannot bind TCP to port {port}: {e}")
            if port == ports_to_try[-1]:
                print("⚠️ TCP server failed, continuing with UDP only")
                return None, None
            print(f"🔄 Trying next TCP port: {ports_to_try[ports_to_try.index(port) + 1]}")
    
    print("⚠️ TCP server unavailable, continuing with UDP only")
    return None, None

def udp_server():
    """UDP server with port fallback"""
    try:
        sock, actual_port = create_udp_socket()
        filter = SimpleDNSFilter()
        
        print(f"✅ UDP DNS server running on [::]:{actual_port} (IPv4 & IPv6)")
        while True:
            try:
                data, addr = sock.recvfrom(512)
                response = filter.handle_dns_request(data)
                sock.sendto(response, addr)
            except Exception as e:
                print(f"UDP processing error: {e}")
                
    except Exception as e:
        print(f"❌ Failed to start UDP server: {e}")
        sys.exit(1)

def tcp_server():
    """TCP server with port fallback"""
    try:
        sock, actual_port = create_tcp_socket()
        if sock is None:
            return  # TCP not available, skip quietly
        
        filter = SimpleDNSFilter()
        
        print(f"✅ TCP DNS server running on [::]:{actual_port} (IPv4 & IPv6)")
        while True:
            try:
                conn, addr = sock.accept()
                data = conn.recv(1024)
                if data:
                    dns_data = data[2:] if len(data) > 2 else data
                    response = filter.handle_dns_request(dns_data)
                    conn.send(b"\x00" + bytes([len(response)]) + response)
                conn.close()
            except Exception as e:
                print(f"TCP processing error: {e}")
                
    except Exception as e:
        print(f"⚠️ TCP server error: {e}")
        # Don't exit, UDP is main service

def get_active_ports():
    """Get list of ports that are actually listening"""
    active_ports = []
    for port in [53, 5353, 5354, 5355]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as test_sock:
                test_sock.connect(('127.0.0.1', port))
                active_ports.append(port)
        except:
            pass
    return active_ports

if __name__ == '__main__':
    print("🚀 Starting DNS No-AAAA Server...")
    print("📋 Configuration:")
    print(f"   - Upstream DNS: {os.getenv('UPSTREAM_DNS', '8.8.8.8')}")
    print(f"   - Debug Mode: {os.getenv('DEBUG', 'false')}")
    
    # Start servers in threads
    udp_thread = threading.Thread(target=udp_server, daemon=True)
    tcp_thread = threading.Thread(target=tcp_server, daemon=True)
    
    udp_thread.start()
    tcp_thread.start()
    
    # Wait a bit for servers to start
    import time
    time.sleep(2)
    
    # Display active ports
    active_ports = get_active_ports()
    if active_ports:
        print(f"✅ DNS No-AAAA server started successfully!")
        print(f"📡 Listening on ports: {', '.join(map(str, active_ports))}")
        print("🔍 Ready to block AAAA queries!")
    else:
        print("❌ No ports available for listening")
        sys.exit(1)
    
    # Keep main thread alive
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down DNS server...")
