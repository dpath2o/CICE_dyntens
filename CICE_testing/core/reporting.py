"""Machine-readable gate evidence and a complete human-readable checker transcript."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
from .. import __version__


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def source_state(repo):
    state = {"repo": str(repo)}
    for label, command in (("commit", ["git", "rev-parse", "HEAD"]),
                           ("status", ["git", "status", "--porcelain"]),
                           ("diff", ["git", "diff", "HEAD"])):
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
        state[label] = result.stdout.strip() if result.returncode == 0 else None
    return state


class EvidenceWorkflow:
    """Optional evidence capture; exceptions remain failures and are re-raised."""
    gate = "unspecified"
    pending = ()

    def run_with_evidence(self, action, output):
        if action != "analyse":
            raise ValueError("evidence is supported only for analyse")
        root = Path(output).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        record = {"schema_version": 1, "package_version": __version__,
                  "gate": self.gate, "status": "FAIL", "pending": list(self.pending),
                  "utc": datetime.now(timezone.utc).isoformat(),
                  "runs": str(self.spec.runs), "source": source_state(self.spec.repo),
                  "python": sys.version, "executables": {}}
        for path in sorted(self.spec.runs.glob("dt_" + self.gate.lower().replace('.', '') + "*/cice")):
            record["executables"][str(path)] = sha256(path)
        transcript = io.StringIO()
        try:
            with redirect_stdout(transcript):
                result = self.analyse()
            record["status"] = "PASS"
            return result
        except Exception as exc:
            record["error"] = str(exc)
            raise
        finally:
            log = root / (self.gate.lower().replace('.', '') + "-analysis.txt")
            log.write_text(transcript.getvalue())
            print(transcript.getvalue(), end="")
            record["transcript"] = str(log)
            record["transcript_sha256"] = sha256(log)
            (root / (self.gate.lower().replace('.', '') + "-validation.json")).write_text(
                json.dumps(record, indent=2, allow_nan=False) + "\n")
