# Tundra-Map print worker

Runs on a Raspberry Pi with the Brother QL-810WC. Keeps one Postgres
connection open, `LISTEN print_jobs`, and prints as soon as a job is queued.

## Install

```bash
cd /srv/repo/tundra-map/pi-print-worker
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# printer udev rules so the worker doesn't need root
sudo install -m 0644 99-brother-ql.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
sudo usermod -aG dialout kaan   # if not already

# env file
sudo tee /etc/tundra-print.env >/dev/null <<'EOF'
DATABASE_URL=postgres://user:pass@host:5432/frz
PUBLIC_BASE_URL=https://frz.up.railway.app
PRINTER_MODEL=QL-810W
PRINTER_BACKEND=pyusb
PRINTER_IDENT=usb://0x04f9:0x209c
LABEL_SIZE=29x90
EOF
sudo chmod 600 /etc/tundra-print.env

# systemd
sudo install -m 0644 systemd/tundra-print.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tundra-print
journalctl -u tundra-print -f
```

## Dry-run without printer

`python worker.py` will print a `pyusb` error each time a job arrives if no
printer is attached. To render labels to files instead, set
`PRINTER_BACKEND=file` (not implemented yet — see TODO).

## Testing render only

```bash
.venv/bin/python -c "
from render import render_label
from datetime import datetime
img = render_label(url='https://frz.example/i/abcd1234?k=x',
                   name='Beef Stew', added_at=datetime.now(), size='29x90')
img.save('/tmp/label.png')
"
```
