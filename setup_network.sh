#!/bin/bash

###############################################################################
# NAVAIR Network Setup Script - WiFi Safe, Network Router
#
# This script configures:
# • eth0: Pi ↔ Printer (192.168.1.x network, Pi is DHCP server)
# • eth1: Pi ↔ Laptop (192.168.2.x network, Pi is DHCP server)  
# • wlan0: Keeps working for Pi's internet access (UNTOUCHED)
#
# Routing:
# • Laptop CAN access printer (192.168.1.50) for Cura Slicer
# • Laptop CAN access Pi dashboard/API (192.168.2.1)
# • Laptop CANNOT access internet via Pi (use separate WiFi)
#
# Printer MAC: 00:30:d6:39:df:f9 → Static IP: 192.168.1.50
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Network Configuration
PI_ETH0_IP="192.168.1.1"           # Pi on printer network
PI_ETH1_IP="192.168.2.1"           # Pi on laptop network
PRINTER_MAC="00:30:d6:39:df:f9"    # Your Ultimaker S5 MAC
PRINTER_STATIC_IP="192.168.1.50"   # Printer's assigned IP

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   NAVAIR Network Setup (Router Mode)      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run with sudo${NC}"
    exit 1
fi

# Backup existing configs
BACKUP_DIR="/home/navair/network_backups_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo -e "${YELLOW}Creating backups in: $BACKUP_DIR${NC}"

[ -f /etc/dhcpcd.conf ] && cp /etc/dhcpcd.conf "$BACKUP_DIR/"
[ -f /etc/dnsmasq.conf ] && cp /etc/dnsmasq.conf "$BACKUP_DIR/"
echo -e "${GREEN}✓ Backups created${NC}\n"

###############################################################################
# Step 1: Detect Network Manager
###############################################################################

echo -e "${YELLOW}[1/7] Detecting network configuration system...${NC}"

# Detect which network manager is in use
if systemctl is-active --quiet NetworkManager; then
    NET_MGR="NetworkManager"
    echo "  Using: NetworkManager"
elif systemctl is-active --quiet dhcpcd; then
    NET_MGR="dhcpcd"
    echo "  Using: dhcpcd"
elif systemctl is-active --quiet systemd-networkd; then
    NET_MGR="systemd-networkd"
    echo "  Using: systemd-networkd"
else
    NET_MGR="manual"
    echo "  Using: manual configuration"
fi

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    Using Cura Slicer with This Setup      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}1. Add Printer in Cura:${NC}"
echo "   • Open Cura → Settings → Printers → Add Printer"
echo "   • Select 'Ultimaker S5' from network printers"
echo "   • Or manually add with IP: ${BLUE}192.168.1.50${NC}"
echo ""
echo -e "${GREEN}2. Print from Cura:${NC}"
echo "   • Slice your model in Cura"
echo "   • Click 'Print via Network'"
echo "   • Select your Ultimaker S5"
echo "   • Monitor print via dashboard: ${BLUE}http://192.168.2.1:3000${NC}"
echo ""
echo -e "${YELLOW}Note: Laptop must be connected via Ethernet to access printer${NC}"
echo ""

###############################################################################
# Step 2: Configure Static IPs
###############################################################################

echo -e "${YELLOW}[2/7] Configuring static IPs on eth0 and eth1...${NC}"

if [ "$NET_MGR" = "NetworkManager" ]; then
    # Use NetworkManager nmcli
    echo "  Configuring via NetworkManager..."
    
    # Configure eth0
    nmcli connection delete "Wired connection 1" 2>/dev/null || true
    nmcli connection delete "eth0" 2>/dev/null || true
    nmcli connection add type ethernet con-name eth0 ifname eth0 \
        ipv4.method manual \
        ipv4.addresses 192.168.1.1/24 \
        ipv6.method disabled
    
    # Configure eth1
    nmcli connection delete "Wired connection 2" 2>/dev/null || true
    nmcli connection delete "eth1" 2>/dev/null || true
    nmcli connection add type ethernet con-name eth1 ifname eth1 \
        ipv4.method manual \
        ipv4.addresses 192.168.2.1/24 \
        ipv6.method disabled
    
    echo "  Activating connections..."
    nmcli connection up eth0 2>/dev/null || true
    nmcli connection up eth1 2>/dev/null || true
    
    # Wait for interfaces to come up
    sleep 3
    
elif [ "$NET_MGR" = "dhcpcd" ]; then
    # Use dhcpcd.conf (old method)
    echo "  Configuring via dhcpcd.conf..."
    
    # Remove any existing eth0/eth1 config to avoid duplicates
    sed -i '/# NAVAIR Configuration/,/^$/d' /etc/dhcpcd.conf 2>/dev/null || true
    sed -i '/interface eth0/,/^$/d' /etc/dhcpcd.conf 2>/dev/null || true
    sed -i '/interface eth1/,/^$/d' /etc/dhcpcd.conf 2>/dev/null || true
    
    # Add new configuration
    cat >> /etc/dhcpcd.conf <<'EOF'

# NAVAIR Configuration - Printer Network (eth0)
interface eth0
static ip_address=192.168.1.1/24
nogateway
noipv6

# NAVAIR Configuration - Laptop Network (eth1)  
interface eth1
static ip_address=192.168.2.1/24
nogateway
noipv6
EOF

else
    # Manual configuration using ip command
    echo "  Configuring manually with ip command..."
    ip addr add 192.168.1.1/24 dev eth0 2>/dev/null || true
    ip link set eth0 up
    ip addr add 192.168.2.1/24 dev eth1 2>/dev/null || true
    ip link set eth1 up
fi

echo -e "${GREEN}✓ Static IPs configured (WiFi untouched)${NC}\n"

###############################################################################
# Step 3: Install and Configure dnsmasq (DHCP Server)
###############################################################################

echo -e "${YELLOW}[3/7] Setting up DHCP server...${NC}"

# Install dnsmasq if needed
if ! dpkg -l | grep -q "^ii  dnsmasq"; then
    echo "  Installing dnsmasq..."
    apt-get update -qq
    apt-get install -y dnsmasq
    echo "  dnsmasq installed"
else
    echo "  dnsmasq already installed"
fi

# Stop services that might conflict
systemctl stop dnsmasq 2>/dev/null || true

# Disable systemd-resolved if it's running (conflicts with dnsmasq)
if systemctl is-active --quiet systemd-resolved; then
    echo "  Detected systemd-resolved conflict, configuring..."
    # Make systemd-resolved not bind to port 53
    mkdir -p /etc/systemd/resolved.conf.d
    cat > /etc/systemd/resolved.conf.d/navair.conf <<'EOF'
[Resolve]
DNSStubListener=no
EOF
    systemctl restart systemd-resolved
    echo "  systemd-resolved configured to not conflict"
fi

# Create dnsmasq.d directory if it doesn't exist
mkdir -p /etc/dnsmasq.d

# Ensure main dnsmasq.conf includes the .d directory
if ! grep -q "^conf-dir=/etc/dnsmasq.d" /etc/dnsmasq.conf 2>/dev/null; then
    echo "conf-dir=/etc/dnsmasq.d/,*.conf" >> /etc/dnsmasq.conf
    echo "  Added dnsmasq.d include to main config"
fi

# Create NAVAIR-specific dnsmasq config
cat > /etc/dnsmasq.d/navair.conf <<EOF
# NAVAIR DHCP Configuration
# CRITICAL: Only listen on eth0 and eth1 (NOT wlan0)
interface=eth0
interface=eth1

# Use bind-dynamic instead of bind-interfaces to handle interfaces coming up later
bind-dynamic

# Don't fail if interfaces aren't ready yet
no-ping

# Don't use /etc/resolv.conf (avoid conflicts)
no-resolv

# Use Google DNS for upstream queries
server=8.8.8.8
server=8.8.4.4

# Printer Network (eth0 - 192.168.1.x)
dhcp-range=interface:eth0,192.168.1.10,192.168.1.100,255.255.255.0,24h
dhcp-option=interface:eth0,option:router,192.168.1.1
dhcp-option=interface:eth0,option:dns-server,192.168.1.1

# Printer Static IP Assignment (by MAC address)
dhcp-host=${PRINTER_MAC},${PRINTER_STATIC_IP},ultimaker-s5,infinite

# Laptop Network (eth1 - 192.168.2.x)
dhcp-range=interface:eth1,192.168.2.10,192.168.2.50,255.255.255.0,24h
dhcp-option=interface:eth1,option:router,192.168.2.1
dhcp-option=interface:eth1,option:dns-server,192.168.2.1

# General settings
log-queries
log-dhcp
EOF

# Create a helper script for laptops to easily add the route
cat > /usr/local/bin/navair-laptop-setup.sh <<'SETUPEOF'
#!/bin/bash
# NAVAIR Laptop Setup Script
# Run this once on any laptop connecting to the NAVAIR system

echo "=== NAVAIR Laptop Network Setup ==="
echo ""
echo "Detecting operating system..."

if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "darwin"* ]]; then
    # Linux or Mac
    echo "Linux/Mac detected"
    echo "Adding route: 192.168.1.0/24 via 192.168.2.1"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Mac
        sudo route -n add 192.168.1.0/24 192.168.2.1
    else
        # Linux
        sudo ip route add 192.168.1.0/24 via 192.168.2.1
    fi
    
    echo "✓ Route added successfully"
    echo ""
    echo "To make permanent, add to /etc/network/interfaces or NetworkManager"
    
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows (Git Bash or similar)
    echo "Windows detected - please run in Command Prompt as Administrator:"
    echo ""
    echo "route -p ADD 192.168.1.0 MASK 255.255.255.0 192.168.2.1 METRIC 10"
    echo ""
else
    echo "Unknown OS. Manually add route:"
    echo "Destination: 192.168.1.0/24"
    echo "Gateway: 192.168.2.1"
fi

echo ""
echo "Test connection:"
echo "  ping 192.168.2.1   (Pi)"
echo "  ping 192.168.1.50  (Printer)"
SETUPEOF

chmod +x /usr/local/bin/navair-laptop-setup.sh

echo "  Created laptop setup helper script at /usr/local/bin/navair-laptop-setup.sh"

echo -e "${GREEN}✓ DHCP server configured${NC}\n"

###############################################################################
# Step 4: Enable Network Routing (Laptop ↔ Printer via Pi)
###############################################################################

echo -e "${YELLOW}[4/7] Configuring network routing...${NC}"

# Install iptables if not present
if ! command -v iptables &> /dev/null; then
    echo "  Installing iptables..."
    apt-get update -qq
    apt-get install -y iptables
    echo "  iptables installed"
fi

# Ensure sysctl.conf exists
if [ ! -f /etc/sysctl.conf ]; then
    touch /etc/sysctl.conf
    echo "  Created /etc/sysctl.conf"
fi

# Enable IP forwarding between eth0 and eth1 (NOT to internet)
if grep -q "net.ipv4.ip_forward" /etc/sysctl.conf; then
    sed -i 's/^#net.ipv4.ip_forward=.*/net.ipv4.ip_forward=1/' /etc/sysctl.conf
    sed -i 's/^net.ipv4.ip_forward=.*/net.ipv4.ip_forward=1/' /etc/sysctl.conf
else
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi

# Apply immediately
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1

# Clear any existing NAVAIR rules
iptables -D FORWARD -i eth1 -o eth0 -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i eth0 -o eth1 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i eth1 -o wlan0 -j DROP 2>/dev/null || true

# Allow routing between eth0 (printer) and eth1 (laptop)
iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -o eth1 -m state --state RELATED,ESTABLISHED -j ACCEPT

# Block laptop from accessing internet via Pi (only local networks)
iptables -A FORWARD -i eth1 -o wlan0 -j DROP

# Save iptables rules
if command -v netfilter-persistent &> /dev/null; then
    netfilter-persistent save 2>/dev/null || true
else
    # Install iptables-persistent to save rules
    echo "  Installing iptables-persistent..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent 2>/dev/null || true
    netfilter-persistent save 2>/dev/null || true
fi

echo -e "${GREEN}✓ Network routing enabled (laptop can access printer)${NC}\n"

###############################################################################
# Step 5: Restart Services
###############################################################################

echo -e "${YELLOW}[5/7] Restarting network services...${NC}"

if [ "$NET_MGR" = "NetworkManager" ]; then
    echo "  Restarting NetworkManager..."
    systemctl restart NetworkManager
    sleep 2
elif [ "$NET_MGR" = "dhcpcd" ]; then
    echo "  Restarting dhcpcd..."
    systemctl restart dhcpcd
    sleep 3
else
    echo "  Network configured manually (no restart needed)"
    sleep 1
fi

# Always restart dnsmasq
echo "  Starting dnsmasq..."
if systemctl list-unit-files | grep -q dnsmasq.service; then
    systemctl enable dnsmasq 2>/dev/null || echo "  Warning: Could not enable dnsmasq"
    
    # Check if port 53 is in use before starting
    if ss -tuln | grep -q ":53 "; then
        echo -e "  ${YELLOW}Warning: Port 53 already in use${NC}"
        PORT_USER=$(ss -tulnp | grep ":53 " | head -1)
        echo "  $PORT_USER"
    fi
    
    systemctl restart dnsmasq
    sleep 2
    
    if systemctl is-active --quiet dnsmasq; then
        echo -e "  dnsmasq:         ${GREEN}RUNNING${NC}"
    else
        echo -e "  dnsmasq:         ${RED}FAILED TO START${NC}"
        echo ""
        echo -e "${YELLOW}Checking dnsmasq logs:${NC}"
        journalctl -u dnsmasq -n 10 --no-pager
        echo ""
        echo -e "${YELLOW}Checking port 53:${NC}"
        ss -tulnp | grep ":53 " || echo "  Port 53 is free"
        echo ""
        echo -e "${RED}dnsmasq failed - manual troubleshooting needed${NC}"
        echo "Run: sudo systemctl status dnsmasq"
    fi
else
    echo -e "  ${RED}dnsmasq service not found. Installing...${NC}"
    apt-get update -qq
    apt-get install -y dnsmasq
    systemctl enable dnsmasq
    systemctl start dnsmasq
fi

echo -e "${GREEN}✓ Services restarted${NC}\n"

###############################################################################
# Step 5.5: Verify SSH is Enabled
###############################################################################

echo -e "${YELLOW}[5.5/7] Verifying SSH access...${NC}"

# Ensure SSH is enabled and running
if systemctl is-active --quiet ssh; then
    echo -e "  SSH service:     ${GREEN}RUNNING${NC}"
else
    echo "  Enabling SSH..."
    systemctl enable ssh
    systemctl start ssh
    echo -e "  SSH service:     ${GREEN}STARTED${NC}"
fi

# Check if SSH is listening
SSH_PORT=$(ss -tlnp | grep :22 | wc -l)
if [ "$SSH_PORT" -gt 0 ]; then
    echo -e "  SSH port 22:     ${GREEN}LISTENING${NC}"
else
    echo -e "  SSH port 22:     ${RED}NOT LISTENING${NC}"
fi

echo ""

###############################################################################
# Step 6: Verify Configuration
###############################################################################

echo -e "${YELLOW}[6/7] Verifying network configuration...${NC}"

# Check if interfaces have correct IPs
ETH0_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "NOT SET")
ETH1_IP=$(ip -4 addr show eth1 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "NOT SET")
WLAN0_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "NOT SET")

echo "Interface Status:"
echo "  eth0 (Printer):  $ETH0_IP"
echo "  eth1 (Laptop):   $ETH1_IP"
echo "  wlan0 (WiFi):    $WLAN0_IP"

# Check dnsmasq
if systemctl is-active --quiet dnsmasq; then
    echo -e "  dnsmasq:         ${GREEN}RUNNING${NC}"
else
    echo -e "  dnsmasq:         ${RED}STOPPED${NC}"
fi

echo ""

###############################################################################
# Step 7: Test Connections
###############################################################################

echo -e "${YELLOW}[7/7] Testing connections...${NC}"

# Test printer (may not respond until it's powered on and connected)
echo -n "  Printer (${PRINTER_STATIC_IP}): "
if timeout 2 ping -c 1 ${PRINTER_STATIC_IP} &>/dev/null; then
    echo -e "${GREEN}REACHABLE${NC}"
else
    echo -e "${YELLOW}NOT RESPONDING (power on printer and wait)${NC}"
fi

echo ""

###############################################################################
# Display Configuration Summary
###############################################################################

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Configuration Complete!             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Network Setup:${NC}"
echo "  ┌─ eth0 (Printer Network)"
echo "  │   • Pi IP:        192.168.1.1"
echo "  │   • Printer IP:   192.168.1.50 (static)"
echo "  │   • Printer MAC:  00:30:d6:39:df:f9"
echo "  │"
echo "  ├─ eth1 (Laptop Network)"
echo "  │   • Pi IP:        192.168.2.1"  
echo "  │   • Laptop IP:    192.168.2.10-50 (DHCP)"
echo "  │"
echo "  ├─ Routing: ENABLED"
echo "  │   • Laptop CAN reach printer (192.168.1.50)"
echo "  │   • Laptop CANNOT access internet via Pi"
echo "  │"
echo "  └─ wlan0 (Internet - Pi Only)"
echo "      • WiFi IP:     $WLAN0_IP"
echo ""
echo -e "${GREEN}Access from Laptop:${NC}"
echo "  • Pi Dashboard:    ${BLUE}http://192.168.2.1:3000${NC}"
echo "  • Pi Backend API:  ${BLUE}http://192.168.2.1:8000${NC}"
echo "  • SSH into Pi:     ${BLUE}ssh navair@192.168.2.1${NC}"
echo ""
echo -e "${YELLOW}⚠️  One-Time Laptop Setup Required:${NC}"
echo "  To access printer (${BLUE}192.168.1.50${NC}), run this command on laptop:"
echo ""
echo -e "  ${GREEN}Windows (Command Prompt as Admin):${NC}"
echo "    ${BLUE}route -p ADD 192.168.1.0 MASK 255.255.255.0 192.168.2.1 METRIC 10${NC}"
echo ""
echo -e "  ${GREEN}Mac:${NC}"
echo "    ${BLUE}sudo route -n add 192.168.1.0/24 192.168.2.1${NC}"
echo ""
echo -e "  ${GREEN}Linux:${NC}"
echo "    ${BLUE}sudo ip route add 192.168.1.0/24 via 192.168.2.1${NC}"
echo ""
echo "  Or download helper script from Pi:"
echo "    ${BLUE}scp navair@192.168.2.1:/usr/local/bin/navair-laptop-setup.sh .${NC}"
echo ""
echo -e "${GREEN}Cura Slicer Setup:${NC}"
echo "  • Printer will be discoverable on local network"
echo "  • Add printer with IP: ${BLUE}192.168.1.50${NC}"
echo "  • Ultimaker S5 should appear in Cura's network printers"
echo ""
echo -e "${GREEN}Test Printer API:${NC}"
echo "  ${BLUE}curl http://192.168.1.50/api/v1/system${NC}"
echo ""
echo -e "${YELLOW}Physical Connections:${NC}"
echo "  ✓ Ethernet cable: Pi eth0 → Ultimaker S5"
echo "  ✓ USB-Ethernet adapter → Pi USB port"
echo "  ✓ Ethernet cable: USB adapter → Laptop"
echo ""
echo -e "${YELLOW}Laptop Setup:${NC}"
echo "  1. Set Ethernet adapter to DHCP (Obtain IP automatically)"
echo "  2. Laptop will get: 192.168.2.10-50"
echo "  3. Gateway: 192.168.2.1"
echo "  4. ${BLUE}Add static route (one-time):${NC}"
echo "     Windows: ${BLUE}route -p ADD 192.168.1.0 MASK 255.255.255.0 192.168.2.1${NC}"
echo "     Mac:     ${BLUE}sudo route -n add 192.168.1.0/24 192.168.2.1${NC}"
echo "     Linux:   ${BLUE}sudo ip route add 192.168.1.0/24 via 192.168.2.1${NC}"
echo ""
echo -e "${GREEN}After Adding Route, Laptop Can Access:${NC}"
echo "  • Dashboard:           http://192.168.2.1:3000"
echo "  • Backend API:         http://192.168.2.1:8000"
echo "  • SSH to Pi:           ssh navair@192.168.2.1"
echo "  • Printer Direct:      http://192.168.1.50"
echo "  • Use Cura Slicer:     Printer at 192.168.1.50"
echo "  • ${RED}No internet access${NC} (use WiFi separately)"
echo ""
echo -e "${GREEN}Logs:${NC}"
echo "  DHCP: ${BLUE}sudo tail -f /var/log/syslog | grep dnsmasq${NC}"
echo "  Check DHCP leases: ${BLUE}cat /var/lib/misc/dnsmasq.leases${NC}"
echo "  SSH logs: ${BLUE}sudo tail -f /var/log/auth.log${NC}"
echo ""
echo -e "${RED}IMPORTANT:${NC} If printer doesn't get 192.168.1.50 immediately:"
echo "  1. Power cycle the printer"
echo "  2. Wait 30 seconds for DHCP lease"
echo "  3. Check: ${BLUE}cat /var/lib/misc/dnsmasq.leases${NC}"
echo ""
echo -e "${GREEN}✓ WiFi on Pi remains fully functional for internet!${NC}"
echo -e "${GREEN}✓ Laptop can access both Pi dashboard AND printer directly${NC}"
echo -e "${GREEN}✓ SSH access enabled on all network interfaces${NC}"
echo ""
echo -e "${YELLOW}Test from your laptop after connecting:${NC}"
echo "  1. ${BLUE}ping 192.168.2.1${NC}               # Test Pi connectivity"
echo "  2. ${BLUE}ping 192.168.1.50${NC}              # Test printer connectivity"
echo "  3. ${BLUE}ssh navair@192.168.2.1${NC}         # SSH into Pi"
echo "  4. ${BLUE}curl http://192.168.2.1:8000/api/health${NC}  # Test backend API"
echo "  5. ${BLUE}curl http://192.168.1.50/api/v1/system${NC}   # Test printer API"
echo "  6. Open browser: ${BLUE}http://192.168.2.1:3000${NC}     # Dashboard"
echo "  7. Open browser: ${BLUE}http://192.168.1.50${NC}         # Printer interface"
echo ""