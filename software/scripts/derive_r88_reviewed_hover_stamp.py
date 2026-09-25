"""Print the r88 source-derived stamp without writing files or contacting hardware."""
from pathlib import Path
import json

from derive_r87_reviewed_hover_stamp import derive

if __name__ == "__main__":
    print(json.dumps(derive(Path(__file__).resolve().parents[1],
                            "configured-diagnostic-candidate-r88")))
