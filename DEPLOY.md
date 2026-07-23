# Deploy — La Queta

Operator runbook for the production Oracle Always Free VM. Product/tech intent stays in `PRODUCT.md` / `TECHNICAL_PLAN.md`; **this file is the how-to and live inventory.**

## Live inventory (update when it changes)

| Item | Value |
|------|--------|
| Cloud | Oracle Cloud Infrastructure (OCI), region **eu-frankfurt-1** |
| Instance | `catala` (Ubuntu 24.04) |
| Public IPv4 | `92.5.65.192` (ephemeral — changes if you detach/recreate the public IP) |
| Private IPv4 | `10.0.0.137` |
| VCN / subnet | `vcn-catala` / `subnet-catala` |
| NSG | `catalaNSG` |
| SSH user | `ubuntu` |
| App path | `/home/ubuntu/la-queta` |
| Python venv | `/home/ubuntu/la-queta/.venv` |
| Env file | `/etc/la-queta/env` (`SECRET_KEY`, `DATABASE_URL`) |
| SQLite | `/var/lib/la-queta/app.db` |
| App process | systemd `la-queta.service` → gunicorn `127.0.0.1:8000` |
| Edge | nginx → proxy to gunicorn on port **80** |
| Health | `curl -s http://127.0.0.1/api/health` (on box) or `http://PUBLIC_IP/api/health` |
| Git remote | `git@github.com-la-queta:LiamSeanLaird/la-queta.git` (SSH Host alias) |
| Deploy key | `~/.ssh/la-queta-deploy` (GitHub deploy key, read-only; no personal `id_rsa` on VM) |
| Host firewall | iptables INPUT: allow 22 + 80, then REJECT; persisted via `netfilter-persistent` |

Do **not** commit secrets, private keys, or the SQLite file.

---

## Architecture

```
Internet → OCI NSG (TCP 22, 80[, 443]) → host iptables → nginx :80 → gunicorn :8000 → Flask → SQLite
```

- gunicorn is **localhost-only**; nginx is the public listener.
- Content/schema: `git` + `flask db upgrade` + `python scripts/seed.py` (idempotent seed).
- **Both** OCI NSG **and** host iptables must allow TCP 80 (OCI Ubuntu images often REJECT all non-SSH by default).

---

## OCI networking (required for browser access)

SSH working ≠ HTTP working. Browser timeouts (`ERR_CONNECTION_TIMED_OUT`) almost always mean **ingress not allowed**.

In **`catalaNSG`** (or subnet security list), ensure ingress:

| Source | Protocol | Port | Purpose |
|--------|----------|------|---------|
| your IP `/32` or `0.0.0.0/0` | TCP | 22 | SSH |
| `0.0.0.0/0` (or tighter) | TCP | 80 | HTTP |
| later | TCP | 443 | HTTPS |

Also confirm:

1. Instance has a **public IP** on the VNIC (ephemeral or reserved).
2. Subnet route table sends `0.0.0.0/0` → **Internet Gateway**.
3. On the VM, **iptables** must allow TCP 80 before the catch-all REJECT (see below). `ufw` is usually absent on this image.

Quick checks on the VM:

```bash
curl -sS http://127.0.0.1:8000/api/health    # app up?
curl -sS http://127.0.0.1/api/health         # nginx → app?
sudo systemctl status la-queta nginx
sudo ss -lntp | grep -E ':80|:8000'
sudo iptables -L INPUT -n --line-numbers | grep -E '80|REJECT|22'
```

If localhost `/api/health` works but the public IP times out → **fix NSG and/or iptables**, not the app.

### Host iptables (required on this image)

Typical pattern: accept established / lo / SSH 22, then REJECT everything else. Without an explicit **TCP 80** ACCEPT before REJECT, browsers time out even when nginx listens on `0.0.0.0:80`.

```bash
sudo iptables -L INPUT -n -v --line-numbers
# insert before the REJECT line, e.g. if REJECT is line 6:
sudo iptables -I INPUT 5 -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save
# rules live in /etc/iptables/rules.v4
```

---

## First-time setup (what we did)

Assumes Ubuntu, user `ubuntu`, public subnet + public IP already assigned.

### 1. Clone via deploy key (preferred)

On the VM, generate a dedicated key and add the **public** half as a GitHub **Deploy key** (read-only):

```bash
ssh-keygen -t ed25519 -C "la-queta-deploy" -f ~/.ssh/la-queta-deploy -N ""
cat ~/.ssh/la-queta-deploy.pub   # paste into GitHub → repo Settings → Deploy keys
```

SSH config + remote (Host alias forces this key; do not use a personal laptop `id_rsa` on the VM):

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com-la-queta
  HostName github.com
  User git
  IdentityFile ~/.ssh/la-queta-deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config ~/.ssh/la-queta-deploy

git clone git@github.com-la-queta:LiamSeanLaird/la-queta.git
cd ~/la-queta
# if already cloned with the wrong URL:
# git remote set-url origin git@github.com-la-queta:LiamSeanLaird/la-queta.git
```

### 2. Packages + venv
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip poetry
poetry config virtualenvs.create false
poetry install --only main
```

(No conda on the server.)

### 3. Data dir + env
```bash
sudo mkdir -p /var/lib/la-queta
sudo chown "$USER":"$USER" /var/lib/la-queta

sudo mkdir -p /etc/la-queta
sudo tee /etc/la-queta/env >/dev/null <<EOF
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
DATABASE_URL=sqlite:////var/lib/la-queta/app.db
EOF
sudo chown root:ubuntu /etc/la-queta/env
sudo chmod 640 /etc/la-queta/env
```

Four slashes after `sqlite:` = absolute path.

### 4. Migrate + seed
```bash
cd ~/la-queta
source .venv/bin/activate
set -a && source /etc/la-queta/env && set +a
flask --app wsgi db upgrade
python scripts/seed.py
```

### 5. systemd (`la-queta.service`)
```bash
sudo tee /etc/systemd/system/la-queta.service >/dev/null <<EOF
[Unit]
Description=La Queta
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/la-queta
EnvironmentFile=/etc/la-queta/env
ExecStart=/home/ubuntu/la-queta/.venv/bin/gunicorn -b 127.0.0.1:8000 -w 2 wsgi:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now la-queta
sudo systemctl status la-queta
```

### 6. nginx
```bash
sudo tee /etc/nginx/sites-available/la-queta >/dev/null <<'EOF'
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/la-queta /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 7. Open HTTP in OCI + host firewall
Add **TCP 80** ingress on `catalaNSG`, allow TCP 80 in iptables (above), `netfilter-persistent save`, then visit `http://PUBLIC_IP/`.

---

## Day-2 deploy (current method)

Manual SSH pull-restart. Good enough for a single Always Free box.

```bash
ssh ubuntu@PUBLIC_IP
cd ~/la-queta
git pull
source .venv/bin/activate
poetry install --only main          # if lockfile changed
set -a && source /etc/la-queta/env && set +a
flask --app wsgi db upgrade
python scripts/seed.py              # safe / idempotent
sudo systemctl restart la-queta
curl -sf http://127.0.0.1/api/health && echo OK
```

Rules:

- Deploy from `main` (or a release tag); don’t develop on the VM.
- Never delete `/var/lib/la-queta/app.db` casually — that’s user progress.
- Prefer backup before risky migrate (see below).

---

## Backup

**Primary:** daily on-VM copy (laptop asleep ≠ no backup).  
**Secondary (optional):** pull a copy to your Mac occasionally via `scp`/`rsync`.

### One-shot

```bash
mkdir -p /var/lib/la-queta/backups
sqlite3 /var/lib/la-queta/app.db \
  ".backup '/var/lib/la-queta/backups/app-$(date -u +%Y%m%dT%H%M%SZ).db'"
ls -lt /var/lib/la-queta/backups | head
```

### Daily cron (as `ubuntu`)

```bash
mkdir -p /var/lib/la-queta/backups
crontab -e
```

Add:

```cron
15 3 * * * sqlite3 /var/lib/la-queta/app.db ".backup '/var/lib/la-queta/backups/app-$(date -u +\%Y\%m\%d).db'" && find /var/lib/la-queta/backups -name 'app-*.db' -mtime +14 -delete
```

(03:15 UTC daily; keep 14 days.)

### Restore

```bash
sudo systemctl stop la-queta
cp /var/lib/la-queta/app.db /var/lib/la-queta/app.db.pre-restore
cp /var/lib/la-queta/backups/app-YYYYMMDD.db /var/lib/la-queta/app.db
sudo systemctl start la-queta
curl -sS http://127.0.0.1/api/health
```

### Optional offsite (Mac)

```bash
mkdir -p ~/Backups/la-queta
scp ubuntu@PUBLIC_IP:/var/lib/la-queta/backups/app-*.db ~/Backups/la-queta/
# or rsync -avz ubuntu@PUBLIC_IP:/var/lib/la-queta/backups/ ~/Backups/la-queta/
```

---

## Improvements (roadmap)

Ordered by ROI — do not jump to containers until the loop below hurts.

1. [x] NSG + iptables + health documented (this file)
2. [x] GitHub deploy key (read-only) — no personal SSH key on the box
3. [ ] Daily SQLite backup cron installed (commands above)
4. [ ] `scripts/deploy.sh` (pull → install → migrate → seed → restart → health)
5. [ ] Unit/nginx templates in `deploy/`
6. Reserved public IP / DNS later; HTTPS once there is a domain
7. CI SSH deploy later — still one VM
8. **Skip for now:** Docker/K8s, managed Postgres, multi-instance

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Browser: connection timed out | NSG missing TCP 80; **or** host iptables REJECT without dport 80; or no public IP |
| Browser: connection refused | nginx down / not listening on 80 |
| 502 Bad Gateway | gunicorn/`la-queta` down — `journalctl -u la-queta -n 50` |
| App works on `:8000` curl but not via nginx | sites-enabled / `default` conflict; `nginx -t` |
| Localhost `/api/health` OK, public times out | NSG and/or iptables (both required) |
| Progress lost after redeploy | `DATABASE_URL` pointed at a different file; check `/etc/la-queta/env` |
| `Permission denied` sourcing env | `chmod 640` + `chown root:ubuntu` on `/etc/la-queta/env` |
| `git pull` asks for old `id_rsa` passphrase | remote must use `github.com-la-queta` Host alias + deploy key |
