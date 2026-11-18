# Deploy - La Queta

Operator runbook for the production Oracle Always Free VM.
Product and tech intent stay in `PRODUCT.md` / `TECHNICAL_PLAN.md`; **this file is the how-to and live inventory.**

## Live inventory (update when it changes)

| Item | Value |
|------|--------|
| Cloud | Oracle Cloud Infrastructure (OCI), region **eu-frankfurt-1** |
| Instance | `catala` (Ubuntu 24.04) |
| Public IPv4 | `92.5.65.192` (ephemeral - changes if you detach/recreate the public IP) |
| Private IPv4 | `10.0.0.137` |
| VCN / subnet | `vcn-catala` / `subnet-catala` |
| NSG | `catalaNSG` |
| SSH user | `ubuntu` |
| App path | `/home/ubuntu/la-queta` |
| Python venv | `/home/ubuntu/la-queta/.venv` |
| Env file | `/etc/la-queta/env` (`SECRET_KEY`, `DATABASE_URL`; optional `FEEDBACK_EMAIL`, `PUBLIC_BASE_URL`) |
| SQLite | `/var/lib/la-queta/app.db` |
| App process | systemd `la-queta.service` → gunicorn `127.0.0.1:8000` |
| Edge | nginx → proxy to gunicorn; HTTP **80** (redirects to HTTPS) + HTTPS **443** (`la-queta.com`; `www` redirects to the apex) |
| TLS | Let's Encrypt via certbot (`--nginx`), auto-renewed by the certbot systemd timer |
| Health | App: `curl -s http://127.0.0.1:8000/api/health`. Via edge: `curl -s https://la-queta.com/api/health` (or `-H 'Host: la-queta.com' http://127.0.0.1/api/health`) |
| Share preview | OG/Twitter meta in `base.html`; `static/og-image.png` (1200×630). Origin: `PUBLIC_BASE_URL` (default `https://la-queta.com`). WhatsApp caches previews - re-share or wait after deploy. |
| Git remote | `git@github.com-la-queta:LiamSeanLaird/la-queta.git` (SSH Host alias) |
| Deploy key | `~/.ssh/la-queta-deploy` (GitHub deploy key, read-only; no personal `id_rsa` on VM) |
| Host firewall | iptables INPUT: allow 22, 80 and 443, then REJECT; persisted via `netfilter-persistent` |

Do **not** commit secrets, private keys, or the SQLite file.

---

## Architecture

```
Internet → OCI NSG (TCP 22, 80, 443) → host iptables → nginx :80 / :443 → gunicorn :8000 → Flask → SQLite
```

- gunicorn is **localhost-only**; nginx is the public listener and terminates TLS.
- Content/schema: `git` + `flask db upgrade` + `python scripts/seed.py` (idempotent seed).
- **Both** the OCI NSG **and** host iptables must allow TCP 80 and 443 (OCI Ubuntu images often REJECT all non-SSH traffic by default).
- There is one canonical origin, `https://la-queta.com`, which must match `PUBLIC_BASE_URL`.
  Canonical tags, `robots.txt` and `sitemap.xml` are built from it, and both nginx and the app (`app/www_redirect.py`) send `www.la-queta.com` to it with a 301.

---

## OCI networking (required for browser access)

SSH working ≠ HTTP working.
Browser timeouts (`ERR_CONNECTION_TIMED_OUT`) almost always mean **ingress not allowed**.

In **`catalaNSG`** (or the subnet security list), ensure ingress:

| Source | Protocol | Port | Purpose |
|--------|----------|------|---------|
| your IP `/32` or `0.0.0.0/0` | TCP | 22 | SSH |
| `0.0.0.0/0` (or tighter) | TCP | 80 | HTTP (redirect to HTTPS, certbot renewals) |
| `0.0.0.0/0` (or tighter) | TCP | 443 | HTTPS |

Also confirm:

1. The instance has a **public IP** on the VNIC (ephemeral or reserved).
2. The subnet route table sends `0.0.0.0/0` → **Internet Gateway**.
3. On the VM, **iptables** allows TCP 80 and 443 before the catch-all REJECT (see below).
   `ufw` is usually absent on this image.

Quick checks on the VM:

```bash
curl -sS http://127.0.0.1:8000/api/health              # app up?
curl -sS -H 'Host: la-queta.com' http://127.0.0.1/api/health  # nginx → app?
curl -sS https://la-queta.com/api/health               # public HTTPS
sudo systemctl status la-queta nginx
sudo ss -lntp | grep -E ':80|:443|:8000'
sudo iptables -L INPUT -n --line-numbers | grep -E '80|443|REJECT|22'
```

If localhost `/api/health` works but the public IP times out → **fix NSG and/or iptables**, not the app.

### Host iptables (required on this image)

Typical pattern: accept established / lo / SSH 22, then REJECT everything else.
Without explicit **TCP 80** and **TCP 443** ACCEPT rules before the REJECT, browsers time out even when nginx is listening.

```bash
sudo iptables -L INPUT -n -v --line-numbers
# insert before the REJECT line, e.g. if REJECT is line 6:
sudo iptables -I INPUT 5 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
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

SSH config + remote (the Host alias forces this key; do not use a personal laptop `id_rsa` on the VM):

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
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx

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
# Optional: FEEDBACK_EMAIL=you@example.com
# Optional: PUBLIC_BASE_URL=https://la-queta.com
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
sudo cp deploy/la-queta.service /etc/systemd/system/la-queta.service
sudo systemctl daemon-reload
sudo systemctl enable --now la-queta
sudo systemctl status la-queta
```

### 6. Open HTTP and HTTPS in OCI + host firewall
Add **TCP 80** and **TCP 443** ingress on `catalaNSG`, allow both in iptables (above), and run `netfilter-persistent save`.

### 7. DNS
Point A records for both `la-queta.com` and `www.la-queta.com` at the public IPv4.
certbot (next step) needs both names to resolve to this VM.

### 8. nginx + HTTPS
The repo config `deploy/nginx-la-queta.conf` references the Let's Encrypt certificate, so `nginx -t` fails until the certificate exists.
Start with a temporary HTTP-only site, let certbot issue the certificate, then install the repo config:

```bash
# 1. Temporary HTTP-only site so certbot can answer the HTTP-01 challenge.
sudo tee /etc/nginx/sites-available/la-queta >/dev/null <<'EOF'
server {
    listen 80 default_server;
    server_name la-queta.com www.la-queta.com;

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

# 2. One certificate covering both names. This also creates
#    /etc/letsencrypt/options-ssl-nginx.conf and ssl-dhparams.pem.
sudo certbot --nginx -d la-queta.com -d www.la-queta.com

# 3. Replace certbot's edits with the repo config (HTTP → HTTPS, www → apex).
sudo cp deploy/nginx-la-queta.conf /etc/nginx/sites-available/la-queta
sudo nginx -t && sudo systemctl reload nginx
```

Then visit `https://la-queta.com/`, and check that `http://la-queta.com/` and `https://www.la-queta.com/` both 301 to it.

---

## Day-2 deploy (current method)

On the production VM:

```bash
ssh ubuntu@PUBLIC_IP
cd ~/la-queta
git pull                  # once, to get scripts/deploy.sh if missing
./scripts/deploy.sh       # or: make deploy
# ./scripts/deploy.sh --no-pull   # re-run migrate/seed/restart without pulling
```

What the script does: `git pull --ff-only` → `poetry install --only main` → SQLite pre-deploy backup → `flask db upgrade` → seed → `systemctl restart la-queta` → `curl` `http://127.0.0.1:8000/api/health` (gunicorn directly, so the nginx config does not matter).
Override with `LA_QUETA_HEALTH_URL` if you want to probe through nginx.

Reference configs: `deploy/la-queta.service` and `deploy/nginx-la-queta.conf`.
The deploy script does **not** install them; copy them by hand when they change (see below).

### Applying a changed nginx config

`deploy/nginx-la-queta.conf` now holds the full HTTPS setup (HTTP → HTTPS, `www` → apex, and a `default_server` block that proxies requests by IP).
It is newer than the config on the live box, which was edited by certbot and may differ.
To apply it:

```bash
sudo certbot certificates          # the la-queta.com certificate must list www.la-queta.com too
# if it does not: sudo certbot --nginx -d la-queta.com -d www.la-queta.com --expand
sudo cp /etc/nginx/sites-available/la-queta ~/nginx-la-queta.bak
sudo cp ~/la-queta/deploy/nginx-la-queta.conf /etc/nginx/sites-available/la-queta
sudo nginx -t && sudo systemctl reload nginx
curl -sI https://www.la-queta.com/ | head -3   # expect 301 → https://la-queta.com/
```

If `nginx -t` fails, restore the backup and reload.

Manual equivalent of the deploy script (if you ever need it):

```bash
cd ~/la-queta
git pull
source .venv/bin/activate
poetry install --only main
set -a && source /etc/la-queta/env && set +a
flask --app wsgi db upgrade
python scripts/seed.py
sudo systemctl restart la-queta
curl -sf http://127.0.0.1:8000/api/health && echo OK
```

Rules:

- Deploy from `main` (or a release tag); don't develop on the VM.
- Never delete `/var/lib/la-queta/app.db` casually - that's user progress.
- Prefer a backup before a risky migrate (the deploy script takes a pre-deploy snapshot).
- **Auth:** email + password (Werkzeug hash); regex email shape only - no verification. `./scripts/deploy.sh` runs migrations including `password_hash`.

---

## SEO after deploy

Do this once, after the first deploy that ships `robots.txt`, `sitemap.xml` and the public lessons:

1. Check what a crawler sees: `curl -s https://la-queta.com/robots.txt` should end with `Sitemap: https://la-queta.com/sitemap.xml`, and `curl -s https://la-queta.com/sitemap.xml` should list the home page and every lesson.
2. Register `la-queta.com` in [Google Search Console](https://search.google.com/search-console) as a **Domain** property, verified with the DNS TXT record it gives you.
   A Domain property covers `http`, `https` and `www` in one place.
3. In Search Console → Sitemaps, submit `https://la-queta.com/sitemap.xml`.
4. In Search Console → URL inspection, inspect `https://la-queta.com/` and click **Request indexing**.

After that, Search Console → Pages shows which URLs are indexed.
The sign-in, sign-up and logged-in pages are `noindex` or blocked by `robots.txt` on purpose, so they appear as excluded there.

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
curl -sS http://127.0.0.1:8000/api/health
```

### Optional offsite (Mac)

```bash
mkdir -p ~/Backups/la-queta
scp ubuntu@PUBLIC_IP:/var/lib/la-queta/backups/app-*.db ~/Backups/la-queta/
# or rsync -avz ubuntu@PUBLIC_IP:/var/lib/la-queta/backups/ ~/Backups/la-queta/
```

---

## Improvements (roadmap)

Ordered by ROI - do not jump to containers until the loop below hurts.

1. [x] NSG + iptables + health documented (this file)
2. [x] GitHub deploy key (read-only) - no personal SSH key on the box
3. [x] Daily SQLite backup cron installed (commands above)
4. [x] `scripts/deploy.sh` / `make deploy` (pull → install → backup → migrate → seed → restart → health)
5. [x] Unit/nginx templates in `deploy/`
6. [x] Domain + HTTPS (`la-queta.com`, Let's Encrypt via certbot)
7. Reserved public IP later (the DNS A records break if the ephemeral IP changes)
8. CI SSH deploy later - still one VM
9. **Skip for now:** Docker/K8s, managed Postgres, multi-instance

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Browser: connection timed out | NSG missing TCP 80/443; **or** host iptables REJECT without dport 80/443; or no public IP |
| Browser: connection refused | nginx down / not listening on 80 or 443 |
| Browser: certificate warning on `www` | The certificate does not cover `www.la-queta.com`; `sudo certbot --nginx -d la-queta.com -d www.la-queta.com --expand` |
| 502 Bad Gateway | gunicorn/`la-queta` down - `journalctl -u la-queta -n 50` |
| App works on `:8000` curl but not via nginx | sites-enabled / `default` conflict; `nginx -t` |
| `curl http://127.0.0.1/api/health` → nginx HTML 404 | The live config has no `default_server` block that proxies (certbot left `server_name` as the domain only). Apply `deploy/nginx-la-queta.conf`, or probe `:8000`, send `Host: la-queta.com`, or use `https://la-queta.com/api/health` |
| Localhost `/api/health` OK, public times out | NSG and/or iptables (both required, for 80 and 443) |
| Canonical tags or sitemap show the wrong host | `PUBLIC_BASE_URL` in `/etc/la-queta/env` is not `https://la-queta.com`; fix it and restart `la-queta` |
| Progress lost after redeploy | `DATABASE_URL` pointed at a different file; check `/etc/la-queta/env` |
| `Permission denied` sourcing env | `chmod 640` + `chown root:ubuntu` on `/etc/la-queta/env` |
| `git pull` asks for old `id_rsa` passphrase | remote must use `github.com-la-queta` Host alias + deploy key |
