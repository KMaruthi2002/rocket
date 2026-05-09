"""Poll AMD Dev Cloud (DigitalOcean) until MI300X capacity opens, then claim one.

Usage:
    export AMD_API_TOKEN=dop_v1_...           # personal access token from AMD Dev Cloud
    export AMD_SSH_KEY_FINGERPRINT=...        # md5 fingerprint of your SSH key
    python3 scripts/claim_droplet.py

How to get the token:
    AMD Developer Cloud → API (left nav) → Generate New Token (Read+Write)

How to get the SSH key fingerprint:
    Settings → Security → SSH Keys → click your key → copy the fingerprint
    OR locally: ssh-keygen -E md5 -lf ~/.ssh/id_ed25519.pub | awk '{print $2}' | sed 's/MD5://'

This script tries to create a single MI300X Droplet (1 GPU, 192 GB VRAM, $1.99/hr)
with the ROCm 7.2 + PyTorch quick-start image. Polls every 25s. Stops the
instant a Droplet creation succeeds.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


API_URL = "https://api-amd.digitalocean.com/v2"
POLL_EVERY_S = 25
DROPLET_NAME = "rocket-mi300x"
REGION_CANDIDATES = ["atl1", "tor1", "nyc2"]   # try several
SIZE_CANDIDATES = [                            # the MI300X 1-GPU size slug
    "gpu-mi300x1-192gb",
    "gpu-mi300x-1",
    "gpu-mi300x",
]
IMAGE_CANDIDATES = [
    "gpu-rocm-pytorch-2-6-0-rocm-7-0",
    "gpu-rocm-7-2",
    "gpu-amd-rocm",
]


def request(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode() or "{}")
        except Exception:
            payload = {"raw": str(e)}
        return e.code, payload
    except Exception as e:
        return 0, {"error": str(e)}


def discover(token: str) -> tuple[list[str], list[str]]:
    """Best-effort: list available sizes/images and pick those matching MI300X / ROCm."""
    sizes = []
    images = []
    code, payload = request("GET", "/sizes", token)
    if code == 200:
        for s in payload.get("sizes", []):
            slug = s.get("slug", "")
            if "mi300x" in slug.lower() and "1gpu" not in slug.lower():
                sizes.append(slug)
        # also keep MI300X x1 specifically
        for s in payload.get("sizes", []):
            slug = s.get("slug", "")
            if "mi300x" in slug.lower() and ("1" in slug or "single" in slug.lower()):
                if slug not in sizes:
                    sizes.insert(0, slug)
    code, payload = request("GET", "/images?type=distribution&per_page=200", token)
    if code == 200:
        for i in payload.get("images", []):
            slug = i.get("slug") or ""
            name = (i.get("name") or "").lower()
            if "rocm" in slug.lower() or "rocm" in name or "pytorch" in slug.lower():
                images.append(slug or i.get("id"))
    return sizes or SIZE_CANDIDATES, images or IMAGE_CANDIDATES


def try_create(token: str, ssh_fp: str, size: str, image: str, region: str) -> tuple[bool, dict]:
    body = {
        "name": DROPLET_NAME,
        "region": region,
        "size": size,
        "image": image,
        "ssh_keys": [ssh_fp],
        "backups": False,
        "ipv6": False,
        "monitoring": True,
        "tags": ["rocket", "hackathon"],
    }
    code, payload = request("POST", "/droplets", token, body)
    if code in (200, 201, 202):
        return True, payload
    # 422 = capacity / size unavailable; try next combo
    return False, {"code": code, "payload": payload, "tried": {"size": size, "image": image, "region": region}}


def wait_for_active(token: str, droplet_id: int, timeout_s: int = 300) -> dict | None:
    start = time.time()
    while time.time() - start < timeout_s:
        code, payload = request("GET", f"/droplets/{droplet_id}", token)
        if code == 200:
            d = payload.get("droplet", {})
            if d.get("status") == "active":
                return d
        time.sleep(8)
    return None


def public_ip(d: dict) -> str | None:
    for net in d.get("networks", {}).get("v4", []):
        if net.get("type") == "public":
            return net.get("ip_address")
    return None


def main():
    token = os.environ.get("AMD_API_TOKEN", "").strip()
    ssh_fp = os.environ.get("AMD_SSH_KEY_FINGERPRINT", "").strip()
    if not token:
        print("✗ AMD_API_TOKEN not set", file=sys.stderr)
        sys.exit(2)
    if not ssh_fp:
        print("✗ AMD_SSH_KEY_FINGERPRINT not set", file=sys.stderr)
        sys.exit(2)

    print("→ discovering MI300X sizes + ROCm images…")
    sizes, images = discover(token)
    print(f"  sizes:  {sizes}")
    print(f"  images: {images[:6]}{'…' if len(images) > 6 else ''}")

    print(f"→ polling for capacity every {POLL_EVERY_S}s. Ctrl-C to stop.")
    attempt = 0
    while True:
        attempt += 1
        for region in REGION_CANDIDATES:
            for size in sizes:
                for image in images:
                    ok, info = try_create(token, ssh_fp, size, image, region)
                    if ok:
                        d = info["droplet"]
                        print(f"\n✓ DROPLET CREATED: id={d['id']}  region={region}  size={size}")
                        print("→ waiting for it to become active…")
                        active = wait_for_active(token, d["id"])
                        ip = public_ip(active or d) or "(provisioning)"
                        print(f"\n┌─────────────────────────────────────────────")
                        print(f"│  ROCKET 🚀  MI300X claimed")
                        print(f"├─────────────────────────────────────────────")
                        print(f"│  region : {region}")
                        print(f"│  size   : {size}")
                        print(f"│  image  : {image}")
                        print(f"│  ip     : {ip}")
                        print(f"│  ssh    : ssh root@{ip}")
                        print(f"└─────────────────────────────────────────────")
                        return
                    # else: try the next combo silently unless it's an auth/quota issue
                    code = info.get("code")
                    msg = json.dumps(info.get("payload", {}))[:160]
                    if code in (401, 403):
                        print(f"✗ auth error ({code}): {msg}")
                        sys.exit(3)
                    if code == 429:
                        print("⏸  rate-limited; sleeping 60s")
                        time.sleep(60)
        ts = time.strftime("%H:%M:%S")
        print(f"  [{ts}] attempt #{attempt}: no capacity in any combo. retry in {POLL_EVERY_S}s.")
        time.sleep(POLL_EVERY_S)


if __name__ == "__main__":
    main()
