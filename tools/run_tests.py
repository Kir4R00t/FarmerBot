"""Run offline tests and write terminal, HTML, and XML coverage reports."""

from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

import coverage


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # Resolve paths from the project, even when invoked from another directory.
    sys.path.insert(0, str(ROOT))
    cov = coverage.Coverage(config_file=str(ROOT / ".coveragerc"))
    cov.set_option("run:source", [str(ROOT / "bot")])
    cov.set_option("run:data_file", str(ROOT / "reports/.coverage"))
    cov.start()
    try:
        # A missing mock must fail locally instead of reaching a real service.
        error = "Live network access is disabled in unit tests"
        with (
            patch.object(socket.socket, "connect", side_effect=AssertionError(error)),
            patch.object(socket.socket, "connect_ex", side_effect=AssertionError(error)),
        ):
            suite = unittest.defaultTestLoader.discover(
                str(ROOT / "tests"), top_level_dir=str(ROOT)
            )
            result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        cov.stop()
        cov.save()
        cov.report()
        cov.html_report(directory=str(ROOT / "reports/coverage"))
        cov.xml_report(outfile=str(ROOT / "reports/coverage.xml"))
        cov.json_report(outfile=str(ROOT / "reports/coverage.json"))
        print(f"\nHTML report: {ROOT / 'reports/coverage/index.html'}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
