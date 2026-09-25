"""Print offline hypothetical correction results. Does not access hardware."""
import json
from rocell.arm.feedback_correction_simulation import scenarios

if __name__=='__main__':
    results=scenarios()
    print(json.dumps(results,indent=2))
    if not all(r['passed'] for r in results):raise SystemExit(1)
