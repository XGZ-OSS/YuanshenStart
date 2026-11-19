# -*- coding: utf-8 -*-
"""Create a GitHub Pages latest.json + first-install update config.

Called from a GitHub Actions Windows runner after building dist/YuanshenStart.exe.
Requires GITHUB_REPOSITORY=OWNER/REPO and GITHUB_REF_NAME=v3.9.
"""
import hashlib
import json
import os
from pathlib import Path
import re

def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    tag = os.environ.get("GITHUB_REF_NAME", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise SystemExit("Missing/invalid GITHUB_REPOSITORY (OWNER/REPO)")
    if not re.fullmatch(r"v\d+(?:\.\d+){1,3}", tag):
        raise SystemExit("Release tag must be v3.9, v3.10, etc.")
    expected_version = tag[1:]
    app_text = Path("app.py").read_text(encoding="utf-8")
    version_match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', app_text, re.M)
    if not version_match or version_match.group(1) != expected_version:
        raise SystemExit(
            f"Version mismatch: tag {tag}, source "
            f"{version_match.group(1) if version_match else '(missing)'}"
        )
    exe = Path("dist/YuanshenStart.exe")
    if not exe.is_file():
        raise SystemExit("Missing dist/YuanshenStart.exe")
    digest = hashlib.sha256()
    with exe.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    owner, name = repo.split("/", 1)
    manifest_url = f"https://{owner}.github.io/{name}/latest.json"
    exe_url = f"https://github.com/{repo}/releases/download/{tag}/YuanshenStart.exe"
    manifest = {
        "version": expected_version,
        "exe_url": exe_url,
        "sha256": digest.hexdigest(),
        "notes": f"沅神启动 {tag} 已发布。新版保留原有 data 积分目录。"
    }
    site = Path("site")
    site.mkdir(exist_ok=True)
    (site / "latest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )
    (site / ".nojekyll").write_text("", encoding="utf-8")
    folder = Path("release")
    folder.mkdir(exist_ok=True)
    (folder / "update_url.txt").write_text(manifest_url + "\n", encoding="utf-8")
    print("EXE SHA-256:", digest.hexdigest())
    print("Stable update manifest:", manifest_url)

if __name__ == "__main__":
    main()
