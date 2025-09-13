import socket
import threading
import os
import sys
import time
from dnslib import DNSRecord, DNSHeader, QTYPE

class SimpleDNSFilter:
    def __init__(self, upstream_dns=None):
        self.upstream_dns = upstream_dns or os.getenv('UPSTREAM_DNS', '8.8.8.8')
        print(f"Using upstream DNS: {self.upstream_dns}")
    
    def handle_dns_request(self, data):
    try:
        request = DNSRecord.parse(data)
        
        # Check for AAAA queries atau ANY queries
        has_aaaa_query = False
        for question in request.questions:
            if question.qtype == QTYPE.AAAA or question.qtype == QTYPE.ANY:
                print(f"🚫 Blocked AAAA/ANY query: {question.qname} (type: {QTYPE[question.qtype]})")
                has_aaaa_query = True
                # Untuk query AAAA atau ANY, kita perlu memberikan response khusus
                if question.qtype == QTYPE.AAAA:
                    # Return empty response untuk AAAA
                    response = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), 
                                       q=question)
                    return response.pack()
        
        # Jika query ANY, kita perlu memfilter record AAAA dari response upstream
        if has_aaaa_query:
            # Forward ke upstream DNS
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(5)
                sock.sendto(data, (self.upstream_dns, 53))
                response_data, _ = sock.recvfrom(4096)  # Perbesar buffer
            
            # Parse response dari upstream
            upstream_response = DNSRecord.parse(response_data)
            
            # Hapus semua record AAAA dari answer section
            filtered_answers = []
            for rr in upstream_response.rr:
                if rr.rtype != QTYPE.AAAA:
                    filtered_answers.append(rr)
            
            # Ganti answer section dengan yang sudah difilter
            upstream_response.rr = filtered_answers
            
            return upstream_response.pack()
        
        # Untuk query lainnya, forward biasa
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.sendto(data, (self.upstream_dns, 53))
            response_data, _ = sock.recvfrom(1024)
        
        return response_data
        
    except Exception as e:
        print(f"Error handling DNS request: {e}")
        return data

def create_udp_socket():
    """Create UDP socket dengan fallback ke higher ports"""
    ports_to_try = [53, 5353, 5354, 5355, 5356, 5357, 5358, 5359, 5360]
    
    for port in ports_to_try:
        try:
            # Try IPv4 first (lebih reliable di GitHub Actions)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', port))
            print(f"✅ UDP successfully bound to port {port} (IPv4)")
            return sock, port
        except OSError as e:
            print(f"❌ Cannot bind UDP IPv4 to port {port}: {e}")
            
            # Try IPv6 sebagai fallback
            try:
                sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                sock.bind(('::', port))
                print(f"✅ UDP successfully bound to port {port} (IPv6)")
                return sock, port
            except OSError as e2:
                print(f"❌ Cannot bind UDP IPv6 to port {port}: {e2}")
                
                if port == ports_to_try[-1]:
                    raise Exception(f"Failed to bind UDP to any port: {ports_to_try}")
                
    raise Exception("No UDP ports available")

def create_tcp_socket():
    """Create TCP socket dengan fallback"""
    ports_to_try = [53, 5353, 5354, 5355]
    
    for port in ports_to_try:
        try:
            # Try IPv4 first
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', port))
            sock.listen(5)
            print(f"✅ TCP successfully bound to port {port} (IPv4)")
            return sock, port
        except OSError as e:
            print(f"❌ Cannot bind TCP IPv4 to port {port}: {e}")
            
            # Try IPv6 fallback
            try:
                sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                sock.bind(('::', port))
                sock.listen(5)
                print(f"✅ TCP successfully bound to port {port} (IPv6)")
                return sock, port
            except OSError as e2:
                print(f"❌ Cannot bind TCP IPv6 to port {port}: {e2}")
                
                if port == ports_to_try[-1]:
                    print("⚠️ TCP server failed, continuing with UDP only")
                    return None, None
    
    return None, None

def udp_server():
    """UDP server dengan comprehensive error handling"""
    try:
        sock, actual_port = create_udp_socket()
        filter = SimpleDNSFilter()
        
        print(f"✅ UDP DNS server running on port {actual_port}")
        while True:
            try:
                data, addr = sock.recvfrom(512)
                response = filter.handle_dns_request(data)
                sock.sendto(response, addr)
            except Exception as e:
                print(f"UDP processing error: {e}")
                time.sleep(1)  # Prevent busy loop on error
                
    except Exception as e:
        print(f"❌ Critical: Failed to start UDP server: {e}")
        print("💡 Tips: Try running with sudo or use different ports")
        sys.exit(1)

def tcp_server():
    """TCP server - optional"""
    try:
        sock, actual_port = create_tcp_socket()
        if sock is None:
            print("⚠️ TCP server unavailable, UDP only mode")
            return
        
        filter = SimpleDNSFilter()
        
        print(f"✅ TCP DNS server running on port {actual_port}")
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
                time.sleep(1)
                
    except Exception as e:
        print(f"⚠️ TCP server error: {e}")
        # Don't exit, UDP is main service

def check_server_ready(port):
    """Check if server is ready to accept connections"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as test_sock:
            test_sock.settimeout(1)
            test_sock.connect(('127.0.0.1', port))
            return True
    except:
        return False

if __name__ == '__main__':
    print("🚀 Starting DNS No-AAAA Server...")
    print("📋 Configuration:")
    print(f"   - Upstream DNS: {os.getenv('UPSTREAM_DNS', '8.8.8.8')}")
    print(f"   - Debug Mode: {os.getenv('DEBUG', 'false')}")
    
    # Start UDP server (mandatory)
    udp_thread = threading.Thread(target=udp_server, daemon=True)
    udp_thread.start()
    
    # Start TCP server (optional)
    tcp_thread = threading.Thread(target=tcp_server, daemon=True)
    tcp_thread.start()
    
    # Wait for server to start and detect port
    time.sleep(3)
    
    # Find which port is actually listening
    active_port = None
    for port in [53, 5353, 5354, 5355, 5356, 5357, 5358, 5359, 5360]:
        if check_server_ready(port):
            active_port = port
            break
    
    if active_port:
        print(f"✅ DNS No-AAAA server started successfully!")
        print(f"📡 Active on port: {active_port}")
        print("🔍 Ready to block AAAA queries!")
        print(f"💡 Test with: dig @127.0.0.1 -p {active_port} google.com AAAA")
    else:
        print("❌ Server started but no ports are listening")
        print("💡 Checking server status...")
        time.sleep(2)
        # Force exit if still not working
        sys.exit(1)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down DNS server...")
