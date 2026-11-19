# Raspberry Pi setup runbook

How to set up the Raspberry Pi 5 that hosts the Family Book Tracker on the home network,
from a blank SSD to a running app. The design and the reasons behind it are in
[spec section 10](../../docs/Family%20Book%20Tracker%20–%20Specification.md#10-hosting-raspberry-pi-on-the-home-network);
this file is the how-to.

You need: the Pi 5 with the NVMe SSD on its M.2 HAT, wired Ethernet to the eero, a PC
with [Raspberry Pi Imager](https://www.raspberrypi.com/software/), a USB M.2 enclosure
(or a spare microSD card, see step 1), and the eero app.

Commands run on the Pi unless they say **(PC)**.

## 1. Install the OS on the SSD

1. **(PC)** Put the SSD in the USB enclosure and open Raspberry Pi Imager.
   - Device: **Raspberry Pi 5**.
   - OS: **Raspberry Pi OS (other) → Raspberry Pi OS Lite (64-bit)**. Lite has no desktop.
   - Storage: the SSD.
2. Choose **Edit settings** (OS customisation) before writing:
   - Hostname: `books`.
   - Username: your admin user; set a password (needed for `sudo`, not for SSH).
   - Wireless LAN: leave off; the Pi is wired.
   - Locale and time zone: yours.
   - Services: **Enable SSH → Allow public-key authentication only**, and paste your
     public key (for example `~/.ssh/id_ed25519.pub`; make one with `ssh-keygen -t ed25519`
     if needed).
3. Write, then fit the SSD to the HAT and power on with no SD card inserted.

If the Pi doesn't boot from the SSD, its bootloader is too old or the HAT needs PCIe
probing. Boot once from an SD card with the same OS, run `sudo rpi-eeprom-update -a`,
reboot, then `sudo raspi-config` → **Advanced Options → Boot Order → NVMe/USB Boot**.
Some third-party HATs also need `PCIE_PROBE=1` added with `sudo rpi-eeprom-config --edit`.

VNC: spec section 10.3 allows VNC temporarily during setup, but this runbook needs only
SSH. If you did install a desktop and VNC, remove them when finished and delete the
port 5900 rule (`sudo ufw delete allow from 192.168.4.0/22 to any port 5900 proto tcp`).

## 2. Network name and fixed address

1. In the eero app, find the Pi (named `books`) and add a **reservation** for it, under
   the network settings' **Reservations & port forwarding** (menu names vary by app
   version). Add **no** port forwarding.
2. While there, **confirm the network range** under the DHCP / NAT settings. The firewall
   rules below assume `192.168.4.0/22` (eero's default). If yours differs, use your range
   everywhere this file says `192.168.4.0/22`.
3. **(PC)** Check the name resolves, then sign in:

   ```bash
   ping -4 books.local
   ssh -4 <user>@books.local        # or ssh <user>@<reserved-ip>
   ```

   Avahi, which advertises `books.local`, is installed and running by default
   (`systemctl status avahi-daemon`). Some Android devices don't resolve `.local`; they
   use the reserved IP instead.

4. Bring the OS up to date and check the clock (HTTPS certificates depend on it):

   ```bash
   sudo apt update && sudo apt full-upgrade -y
   timedatectl                     # "System clock synchronized: yes"
   ```

## 3. SSH: keys only

Imager already set public-key-only sign-in. Make it explicit, so a later package update
can't turn passwords back on:

```bash
sudo tee /etc/ssh/sshd_config.d/10-books.conf >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
sudo sshd -t && sudo systemctl reload ssh
```

**Keep your current session open** and check that a new one still signs in
(`ssh -4 <user>@books.local` from the PC) before you close it.

## 4. Firewall (ufw)

Allowed traffic comes only from the home network. Add the SSH rule **before** enabling
ufw, or you lock yourself out.

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.4.0/22 to any port 22 proto tcp comment 'SSH'
sudo ufw allow from 192.168.4.0/22 to any port 5353 proto udp comment 'mDNS books.local'
sudo ufw allow from 192.168.4.0/22 to any port 80,443 proto tcp comment 'Book tracker via Caddy'
sudo ufw enable
sudo ufw status verbose
```

Two things the rules don't do (spec section 10.3):

- **IPv6:** the rules are IPv4 only, so connect with `ssh -4`, or put
  `AddressFamily inet` in `~/.ssh/config` for this host.
- **Docker ports bypass ufw.** Docker writes its own iptables rules, so the 80/443 rule
  doesn't actually filter Caddy. The real boundaries are in `compose.yaml` (only Caddy
  publishes ports, bound to the Pi's LAN address) and on the router (no port forwarding).

## 5. Automatic security updates

```bash
sudo apt install -y unattended-upgrades apt-listchanges
sudo tee /etc/apt/apt.conf.d/52books-unattended >/dev/null <<'EOF'
// Raspberry Pi's own repository (kernel, firmware, bootloader) as well as Debian's.
Unattended-Upgrade::Origins-Pattern {
        "origin=Raspberry Pi Foundation,codename=${distro_codename},label=Raspberry Pi Foundation";
};
// Kernel updates need a reboot; the containers come back on their own.
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";
EOF
sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
sudo unattended-upgrade --dry-run --debug 2>&1 | grep -E "Allowed origins|Checking"
```

The dry run's "Allowed origins" line should list both Debian's security origin and
`Raspberry Pi Foundation`. Docker's own packages are left out deliberately: update them
by hand (section 9) so a Docker upgrade doesn't restart the app unexpectedly.

## 6. Docker

Install Docker Engine and the Compose plugin from Docker's repository (Raspberry Pi OS
64-bit uses Docker's Debian packages):

```bash
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Cap container log size, so logs can't fill the SSD:

```bash
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
EOF
sudo systemctl restart docker
```

Let your user run Docker without `sudo`, then sign out and back in:

```bash
sudo usermod -aG docker "$USER"
```

Membership of the `docker` group is equivalent to root on the Pi; give it only to the
admin user.

## 7. Deploy the app

1. Get the stack files. The repository is public, so no credentials are needed:

   ```bash
   sudo mkdir -p /opt/books && sudo chown "$USER": /opt/books
   git clone https://github.com/muirjc/books.git /opt/books/repo
   cd /opt/books/repo/deploy/pi
   ```

   (If `git` is missing: `sudo apt install -y git`.)

2. Create the secrets file from the template, readable only by you:

   ```bash
   cp .env.example .env && chmod 600 .env
   openssl rand -hex 32     # run twice: one for POSTGRES_PASSWORD, one for BOOK_TRACKER_SECRET_KEY
   nano .env
   ```

   Fill in `PI_LAN_IP` (the reserved address), the two generated values, and the first
   Admin's login, display name and password. Keep a copy of `.env` in the family password
   manager: without `POSTGRES_PASSWORD` a database backup is harder to restore.

3. Start it:

   ```bash
   docker compose pull
   docker compose up -d
   docker compose ps          # db and app "healthy", proxy "running"
   docker compose logs app    # "Created Admin account ..."
   ```

   PostgreSQL's data goes to `/srv/books/postgres` on the SSD.

4. Remove `BOOK_TRACKER_ADMIN_PASSWORD` from `.env` (leave the line empty). It's only
   used when no Admin exists yet.

5. Export Caddy's root certificate, which every family device must trust before the site
   opens without warnings:

   ```bash
   docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ~/books-root.crt
   ```

   Installing it on each device is task books-euq.8. Then open `https://books.local`
   (or `https://<reserved-ip>`) and sign in as the Admin.

## 8. Check before go-live

- [ ] The eero network range matches the ufw rules (section 2).
- [ ] No port forwarding on the eero.
- [ ] `ssh` with a password is refused: `ssh -4 -o PubkeyAuthentication=no <user>@books.local`.
- [ ] `sudo ufw status` shows only the three LAN rules (no 5900).
- [ ] From the PC, only ports 22, 80 and 443 answer on the Pi's LAN address
      (for example `nmap -4 -p 1-10000 <reserved-ip>`).
- [ ] The app works at `https://books.local` and `https://<reserved-ip>` on a device that
      trusts the root certificate.
- [ ] The nightly backup has run and `books-restore.sh check` passes (section 10).
- [ ] The restic password is in the family password manager.
- [ ] The first USB copy is made and stored away from home (task books-euq.11).

## 9. Routine maintenance

**Update the app** (migrations run when the app starts):

```bash
cd /opt/books/repo && git pull          # picks up changes to the stack files
cd deploy/pi && docker compose pull && docker compose up -d
docker image prune -f
```

**Roll back** by pinning an older image, `BOOKS_TAG=sha-<7-char commit>` in `.env`, then
`docker compose up -d`. Image tags are listed under the repository's **Packages** on
GitHub. A rollback across a database migration may not work; restore the backup taken
before the update instead (section 10).

**Import from Open Library** (spec 002) needs no setup beyond outbound HTTPS, which the
Pi already allows. Requests name only the app; there is no contact setting. If a member
sees "The book site couldn't be reached", Open Library was slow (over 10 s), down or
limiting requests; nothing was changed, and adding books by hand always works. Answers
are kept for 24 hours in the `source_lookup_cache` table, so repeat searches don't call
Open Library again.

**Update Docker** (not covered by automatic updates), when convenient:

```bash
sudo apt update && sudo apt install --only-upgrade docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

**After editing `caddy/Caddyfile`:** `docker compose exec -w /etc/caddy proxy caddy reload`.

**If the GHCR package is ever made private** (task books-euq.10): create a classic
personal access token with only `read:packages`, run
`echo <token> | docker login ghcr.io -u muirjc --password-stdin` once, and note the
token's expiry date here so it gets renewed.

## 10. Backups

Each night at about 02:30, `books-backup.timer` runs
[`backup/books-backup.sh`](backup/books-backup.sh). It:

1. dumps the database;
2. writes a plain copy of the dump to the NAS (`dumps/`, 30 days kept);
3. puts the dump and Caddy's CA keys into an encrypted restic repository on the NAS
   (30 daily snapshots kept);
4. checks the repository, and writes the time to `last-success` on the NAS.

The CA's private keys never reach the NAS unencrypted. If the NAS share isn't mounted,
the backup stops with an error rather than writing to the Pi's own disk.

### Set up (once)

1. **Mount the NAS share** at `/mnt/nas`, from `/etc/fstab`, so it mounts at boot and
   again after a network outage. Use the line for your NAS's protocol:

   ```bash
   sudo apt install -y restic
   sudo mkdir -p /mnt/nas /etc/books
   ```

   Then **either** NFS:

   ```bash
   sudo apt install -y nfs-common
   echo 'nas.local:/volume1/backups /mnt/nas nfs _netdev,x-systemd.automount 0 0' | sudo tee -a /etc/fstab
   ```

   **or** SMB, with `username=...` and `password=...` lines in
   `/etc/books/nas-credentials` (mode 600):

   ```bash
   sudo apt install -y cifs-utils
   echo '//nas.local/backups /mnt/nas cifs credentials=/etc/books/nas-credentials,uid=0,gid=0,file_mode=0600,dir_mode=0700,_netdev,x-systemd.automount 0 0' | sudo tee -a /etc/fstab
   ```

   and finally `sudo systemctl daemon-reload && sudo mount -a`.

   Replace `nas.local` and the share path with your NAS's. Create a folder for the app
   on the share, with the marker file that proves the share is mounted:

   ```bash
   sudo mkdir -p /mnt/nas/books && sudo touch /mnt/nas/books/.books-backup-target
   ```

2. **Settings and the restic password:**

   ```bash
   sudo install -m 600 /opt/books/repo/deploy/pi/backup/backup.env.example /etc/books/backup.env
   openssl rand -base64 32 | sudo tee /etc/books/restic-password >/dev/null
   sudo chmod 600 /etc/books/restic-password
   sudo cat /etc/books/restic-password     # save it in the family password manager now
   ```

   Edit `/etc/books/backup.env` if your paths differ. **Without the restic password the
   encrypted backups can't be restored**, so it must exist somewhere other than the Pi.

3. **Create the repository and install the timer:**

   ```bash
   sudo sh -c 'set -a; . /etc/books/backup.env; set +a; restic init'
   sudo cp /opt/books/repo/deploy/pi/backup/books-backup.service \
           /opt/books/repo/deploy/pi/backup/books-backup.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now books-backup.timer
   sudo systemctl start books-backup.service     # a first backup now
   journalctl -u books-backup -n 20              # ends with "books-backup: done"
   ```

### Restore test (release gate, before go-live)

Restore the latest backup into a scratch database. The live data isn't touched:

```bash
sudo sh -c 'set -a; . /etc/books/backup.env; set +a;
  /opt/books/repo/deploy/pi/backup/books-restore.sh check'
```

It prints row counts for the restored copy next to the live database's, and ends with
`Restore check passed.` Repeat it now and then, for example after each USB copy.

### Restoring for real

Load the settings the same way (`sudo sh -c 'set -a; . /etc/books/backup.env; set +a; ...'`),
then run `books-restore.sh` with one of:

| Situation | Command |
| --- | --- |
| Database lost or damaged | `database --yes` restores the latest snapshot. It stops the app, replaces the database, and starts the app again |
| A particular night | add `--snapshot <id>`; list them with `restic snapshots` |
| No restic password to hand | `database --yes --dump /mnt/nas/books/dumps/books-<time>.dump` uses a plain dump from the NAS |
| Caddy's data volume lost (devices show certificate warnings) | `caddy-ca --yes` puts the old CA back, so devices that trusted it trust it again |

On a new Pi, set it up with sections 1–7 first, then restore.

### Keeping an eye on it

- `systemctl list-timers books-backup.timer` shows the last and next run.
- `/mnt/nas/books/last-success` holds the time of the last good run. If it's more than a
  day or two old, check `journalctl -u books-backup`.
- Before an app update you might want to roll back, take a backup first:
  `sudo systemctl start books-backup.service`.
