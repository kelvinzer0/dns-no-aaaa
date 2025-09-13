FROM python:3.11-alpine

# Install dependencies
RUN pip install --no-cache-dir dnslib

# Create non-root user
RUN adduser -D dnsuser

# Create app directory
WORKDIR /app
COPY dns_server.py ./

# Change ownership to non-root user
RUN chown dnsuser:dnsuser /app

# Switch to non-root user
USER dnsuser

# Expose DNS ports
EXPOSE 53/udp 53/tcp

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD dig @127.0.0.1 google.com A +short || exit 1

# Run the server
CMD ["python", "dns_server.py"]

# Labels
LABEL org.opencontainers.image.title="DNS No-AAAA"
LABEL org.opencontainers.image.description="DNS server that blocks AAAA records"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/kelvinzer0/dns-no-aaaa"
