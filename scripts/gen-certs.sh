#!/bin/bash
# 生成 InfluxDB 自签名 TLS 证书
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERT_DIR="$PROJECT_DIR/secrets"

mkdir -p "$CERT_DIR"

echo "生成 CA 证书..."
openssl req -x509 -new -nodes \
  -newkey rsa:2048 -keyout "$CERT_DIR/ca.key" \
  -days 3650 -out "$CERT_DIR/ca.crt" \
  -subj "/CN=IDM-CA/O=Industrial Data Mining"

echo "生成 InfluxDB 服务端证书..."
openssl req -new -nodes \
  -newkey rsa:2048 -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.csr" \
  -subj "/CN=influxdb/O=Industrial Data Mining"

echo "签名服务端证书..."
openssl x509 -req \
  -in "$CERT_DIR/server.csr" \
  -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
  -CAcreateserial -days 365 -out "$CERT_DIR/server.crt"

rm -f "$CERT_DIR/server.csr" "$CERT_DIR/ca.srl"
chmod 644 "$CERT_DIR/server.crt" "$CERT_DIR/ca.crt"
chmod 600 "$CERT_DIR/server.key" "$CERT_DIR/ca.key"

echo "证书已生成到 $CERT_DIR/"
ls -la "$CERT_DIR/"
