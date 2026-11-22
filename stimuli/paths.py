"""Where the stimulus generator's inputs and outputs live."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STIMULI_DIR = REPO_ROOT / "stimuli"
FACTORS_DIR = STIMULI_DIR / "factors"
FONTS_DIR = STIMULI_DIR / "assets" / "fonts"
