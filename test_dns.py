#!/usr/bin/env python3
import socket
from dnslib import DNSRecord, QTYPE, A

def test_dns_server():
    # Test AAAA query
    query = DNSRecord.question("google.com", "AAAA")
    response = send_dns_query(query.pack(), "127.0.0.1", 53)
    
    parsed = DNSRecord.parse(response)
    print(f"AAAA Response: {parsed.rr}")
    
    # Test A query
    query = DNSRecord.question("google.com", "A")
    response = send_dns_query(query.pack(), "127.0.0.1", 53)
    
    parsed = DNSRecord.parse(response)
    print(f"A Response: {parsed.rr}")

def send_dns_query(data, host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data, (host, port))
    response, _ = sock.recvfrom(1024)
    return response

if __name__ == "__main__":
    test_dns_server()
