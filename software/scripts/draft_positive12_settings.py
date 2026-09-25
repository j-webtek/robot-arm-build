"""Export public +12 experiment settings only; no private staging or hardware."""
import json
from pathlib import Path

from rocell.application.elbow_displacement_experiment import settings_bytes
from rocell.application.held_pair_settings import export_pair_settings


def main():
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(export_pair_settings(root/'runs/wizard-exports', settings_bytes())))


if __name__ == '__main__':
    main()
