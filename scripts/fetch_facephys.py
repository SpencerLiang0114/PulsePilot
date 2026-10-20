"""Fetch the audited upstream source and original checkpoint without redistributing it."""
import subprocess
from pathlib import Path

REVISION = "4d24237e7b14e17429b49d0334f2282b7d2fd159"
ROOT = Path(__file__).resolve().parents[1] / ".vendor" / "open-rppg"


def main():
    if (ROOT / ".git").exists():
        current = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        if current != REVISION:
            raise SystemExit(f"Existing upstream checkout is {current}, expected {REVISION}. Preserve it and inspect.")
    else:
        ROOT.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", str(ROOT)], check=True)
        subprocess.run(["git", "-C", str(ROOT), "fetch", "--depth", "1",
                        "https://github.com/KegangWangCCNU/open-rppg.git", REVISION], check=True)
        subprocess.run(["git", "-C", str(ROOT), "checkout", "--detach", "FETCH_HEAD"], check=True)
    checkpoint = ROOT / "rppg/weights/FacePhys.rlap.weights.h5"
    if not checkpoint.exists() or checkpoint.stat().st_size < 1_000_000:
        raise SystemExit("FacePhys checkpoint missing or incomplete.")
    print(f"Ready: {ROOT}\nRevision: {REVISION}\nRead upstream LICENSE for separate pretrained-model terms.")


if __name__ == "__main__":
    main()
