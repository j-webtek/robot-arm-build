"""Print a reproducible offline matrix; never opens camera, serial or network."""
import json
from rocell.arm.roll_target_variation import simulation_matrix

if __name__ == '__main__':
    print(json.dumps(simulation_matrix(), indent=2))
