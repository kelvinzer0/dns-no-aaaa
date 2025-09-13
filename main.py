import socket
import threading
import os
from dnslib import DNSRecord, DNSHeader, QTYPE

class SimpleDNSFilter:
    def __init__(self, upstream_dns=None):
        # Use custom upstream DNS or default to 8.8.8.8
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
            # Return empty response on error
            return data

def udp_server():
    """UDP server for both IPv4 and IPv6"""
    try:
        # IPv6 socket can handle both IPv4 and IPv6 connections
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.bind(('::', 53))
        filter = SimpleDNSFilter()
        
        print("✅ UDP DNS server running on [::]:53 (IPv4 & IPv6)")
        while True:
            try:
                data, addr = sock.recvfrom(512)
                response = filter.handle_dns_request(data)
                sock.sendto(response, addr)
            except Exception as e:
                print(f"UDP error: {e}")
                
    except Exception as e:
        print(f"Failed to start UDP server: {e}")

def tcp_server():
    """TCP server for both IPv4 and IPv6"""
    try:
        # IPv6 socket can handle both IPv4 and IPv6 connections
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.bind(('::', 53))
        sock.listen(5)
        filter = SimpleDNSFilter()
        
        print("✅ TCP DNS server running on [::]:53 (IPv4 & IPv6)")
        while True:
            try:
                conn, addr = sock.accept()
                data = conn.recv(1024)
                if data:
                    # Remove TCP length prefix (2 bytes)
                    dns_data = data[2:] if len(data) > 2 else data
                    response = filter.handle_dns_request(dns_data)
                    # Add TCP length prefix
                    conn.send(b"\x00" + bytes([len(response)]) + response)
                conn.close()
            except Exception as e:
                print(f"TCP error: {e}")
                
    except Exception as e:
        print(f"Failed to start TCP server: {e}")

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
    
    print("✅ DNS No-AAAA server started successfully!")
    print("📡 Listening on:")
    print("   - UDP: [::]:53 (IPv4 & IPv6)")
    print("   - TCP: [::]:53 (IPv4 & IPv6)")
    print("🔍 Ready to block AAAA queries!")
    
    # Keep main thread alive
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down DNS server...")
