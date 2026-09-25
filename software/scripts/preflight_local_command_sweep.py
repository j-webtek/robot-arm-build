"""Offline command-spacing sweep preflight using a historical example baseline."""
import json
from rocell.arm.local_command_sweep import preflight


if __name__=='__main__':
    print(json.dumps(preflight([-.001533981,0,1.593806039,.007669904,.0398835,3.149262558]),indent=2))
