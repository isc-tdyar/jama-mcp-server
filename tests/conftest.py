"""Root conftest for all tests - imports shared fixtures."""
# Import all fixtures from fixtures/conftest.py
import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Now import fixtures
from fixtures.conftest import *  # noqa: F403, F401
