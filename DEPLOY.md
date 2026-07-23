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
| Health | `curl -s http://127.0.0.1:8000/api/health` (on box) or `http://PUBLIC_IP/api/health` |

Do **not** commit secrets, private keys, or the SQLite file.

---

## Architecture

```
Internet → OCI NSG (TCP 22, 80[, 443]) → nginx :80 → gunicorn :8000 → Flask → SQLite
```

- gunicorn is **localhost-only**; nginx is the public listener.
- Content/schema: `git` + `flask db upgrade` + `python scripts/seed.py` (idempotent seed).

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
3. On the VM, if `ufw` is active: `sudo ufw allow OpenSSH` and `sudo ufw allow 80/tcp`.

Quick checks on the VM:

```bash
curl -sS http://127.0.0.1:8000/api/health    # app up?
curl -sS http://127.0.0.1/api/health         # nginx → app?
sudo systemctl status la-queta nginx
sudo ss -lntp | grep -E ':80|:8000'
```

If localhost works but the public IP times out → **fix the NSG**, not the app.

---

## First-time setup (what we did)

Assumes Ubuntu, user `ubuntu`, public subnet + public IP already assigned.

### 1. Clone
Prefer a **deploy key** (read-only) or HTTPS; avoid copying a personal laptop private key onto the VM long-term.

```bash
git clone git@github.com:LiamSeanLaird/la-queta.git
cd ~/la-queta
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

### 7. Open HTTP in OCI
Add **TCP 80** ingress on `catalaNSG`, then visit `http://PUBLIC_IP/`.

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
curl -sf http://127.0.0.1:8000/api/health && echo OK
```

Rules:

- Deploy from `main` (or a release tag); don’t develop on the VM.
- Never delete `/var/lib/la-queta/app.db` casually — that’s user progress.
- Prefer backup before risky migrate (see below).

---

## Backup (planned / do soon)

```bash
# example one-shot
sqlite3 /var/lib/la-queta/app.db ".backup '/var/lib/la-queta/app-$(date -u +%Y%m%d).db'"
```

Then a daily cron as `ubuntu` or root writing to `/var/lib/la-queta/backups/` (keep last N days). Document the cron line here when installed.

---

## Improvements (roadmap)

Ordered by ROI — do not jump to containers until the loop below hurts.

1. **NSG + health documented** (this file) — stop losing hours to timeouts.
2. **`scripts/deploy.sh` on the VM** (or `make deploy`) — pull → install → migrate → seed → restart → health check.
3. **Unit/nginx templates in `deploy/`** — copy from repo instead of heredocs.
4. **GitHub deploy key** (read-only) instead of a personal SSH key on the box.
5. **Daily SQLite backup cron** + restore notes.
6. **Reserved public IP** if ephemeral churn is annoying; optional DNS later.
7. **HTTPS** (Caddy or certbot + nginx) once there is a domain.
8. **CI SSH deploy** (GitHub Action on push to `main`) — still one VM.
9. **Skip for now:** Docker/K8s, managed Postgres, multi-instance (SQLite doesn’t want writers across hosts).

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Browser: connection timed out | NSG/security list missing TCP 80; or no public IP |
| Browser: connection refused | nginx down / not listening on 80 |
| 502 Bad Gateway | gunicorn/`la-queta` down — `journalctl -u la-queta -n 50` |
| App works on `:8000` curl but not via nginx | sites-enabled / `default` conflict; `nginx -t` |
| Progress lost after redeploy | `DATABASE_URL` pointed at a different file; check `/etc/la-queta/env` |
| `Permission denied` sourcing env | `chmod 640` + `chown root:ubuntu` on `/etc/la-queta/env` |
