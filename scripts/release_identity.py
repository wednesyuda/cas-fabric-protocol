"""Commit and canonical text hashes for a checkout or an exported candidate."""
import hashlib
import json
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path


def hash_sources(root: Path, paths: list[str]) -> dict:
    hashes = {}
    for name in sorted(paths):
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("manifest path outside candidate")
        hashes[name] = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"source_sha256": digest, "files": hashes, "hash_policy": "SHA256 text with CRLF normalized to LF"}


def source_identity(root: Path) -> dict:
    if (root / ".git").exists():
        git = ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root)]
        status = subprocess.check_output(git + ["status", "--porcelain"], text=True)
        if status.strip():
            raise ValueError("release verification requires a clean committed candidate")
        commit = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
        paths = subprocess.check_output(git + ["ls-files"], text=True).splitlines()
        return {"commit": commit, **hash_sources(root, paths)}
    manifest = json.loads((root / "candidate-manifest.json").read_text())
    actual = hash_sources(root, list(manifest["files"]))
    if actual["files"] != manifest["files"] or actual["source_sha256"] != manifest["source_sha256"]:
        raise ValueError("candidate files do not match frozen manifest")
    return {"commit": manifest["commit"], **actual}


def environment_identity() -> dict:
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {name: version(name) for name in ("nats-py", "httpx", "numpy")}}


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parents[1]
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "candidate-manifest.json"
    output.write_text(json.dumps(source_identity(root), indent=2) + "\n")
