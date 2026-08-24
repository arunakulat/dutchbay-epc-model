#!/usr/bin/env bash

# Install the narrow SSH transport required by gh codespace ssh/cp. Apt is
# restricted to the base image's Debian source so an unrelated third-party
# repository cannot break or expand this governed build.

set -euo pipefail

readonly DEBIAN_SOURCES="/etc/apt/sources.list.d/debian.sources"
readonly SSHD_DROP_IN="/etc/ssh/sshd_config.d/00-dutchbay-audit-review.conf"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

[ "$(id -u)" -eq 0 ] || fail "SSH transport installation requires root"
[ -f "$DEBIAN_SOURCES" ] && [ ! -L "$DEBIAN_SOURCES" ] || fail \
  "the pinned base image Debian source is unavailable or unsafe"
[ -x /usr/bin/flock ] || fail "the pinned base image startup lock is unavailable"
[ -d "/etc/ssh" ] || install -d -m 0755 /etc/ssh

export DEBIAN_FRONTEND=noninteractive
rm -rf /var/lib/apt/lists/*
apt-get \
  -o "Dir::Etc::sourcelist=$DEBIAN_SOURCES" \
  -o "Dir::Etc::sourceparts=-" \
  update
apt-get \
  -o "Dir::Etc::sourcelist=$DEBIAN_SOURCES" \
  -o "Dir::Etc::sourceparts=-" \
  install -y --no-install-recommends \
  lsof openssh-client openssh-server

getent group ssh >/dev/null || groupadd ssh
id -u vscode >/dev/null 2>&1 || fail "the pinned base image vscode user is absent"
usermod -aG ssh vscode

install -d -m 0755 /run/sshd /etc/ssh/sshd_config.d
sed -i \
  's/session[[:space:]]\+required[[:space:]]\+pam_loginuid\.so/session optional pam_loginuid.so/g' \
  /etc/pam.d/sshd

cat > "$SSHD_DROP_IN" <<'EOF'
Port 2222
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
HostbasedAuthentication no
GSSAPIAuthentication no
KerberosAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
PermitEmptyPasswords no
GatewayPorts no
UsePAM yes
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
AllowStreamLocalForwarding no
DisableForwarding yes
PermitTunnel no
AllowGroups ssh
SetEnv DUTCHBAY_VENV=/workspaces/.dutchbay-audit-review-venv DUTCHBAY_P03_SOURCE_ROOT=/workspaces/.dutchbay-private/p03/sources PYTHONPATH=/workspaces/dutchbay-epc-model PATH=/workspaces/.dutchbay-audit-review-venv/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin
EOF
chmod 0644 "$SSHD_DROP_IN"

ssh-keygen -A
/usr/sbin/sshd -t
find /etc/ssh -maxdepth 1 -type f -name 'ssh_host_*_key*' -delete
rm -rf /var/lib/apt/lists/*
