import sys
import subprocess

TARGETS = {
    "maps/easy/01_linear_path.txt": 6,
    "maps/easy/02_simple_fork.txt": 8,
    "maps/easy/03_basic_capacity.txt": 6,
    "maps/medium/01_dead_end_trap.txt": 12,
    "maps/medium/02_circular_loop.txt": 15, 
    "maps/medium/03_priority_puzzle.txt": 12,
    "maps/hard/01_maze_nightmare.txt": 30,
    "maps/hard/02_capacity_hell.txt": 35,
    "maps/hard/03_ultimate_challenge.txt": 45,
    "maps/challenger/01_the_impossible_dream.txt": 45 
}


def run_test(map_path: str) -> bool:
    print(f"Testing: {map_path}")
    target = TARGETS.get(map_path, 9999)

    try:
        result = subprocess.run(
            [sys.executable, "main.py", map_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        turns = None
        for line in result.stdout.splitlines():
            if "Total Simulation Turns:" in line:
                turns = int(line.split(":")[-1].strip())
                break
        
        if turns is None:
            print(f"  \033[91m[FAILED]\033[0m Could not parse total turns from output.")
            return False

        if turns <= target:
            print(f"  \033[92m[SUCCESS]\033[0m Completed in {turns} turns (Target: <= {target}).")
            return True
        else:
            print(f"  \033[91m[FAILED]\033[0m Completed in {turns} turns but Target was <= {target}!")
            return False

    except subprocess.CalledProcessError as e:
        print(f"  \033[91m[FAILED]\033[0m Execution crashed with error:\n{e.stderr}")
        return False


def main() -> None:
    print("=" * 60)
    print("          FLY-IN AUTOMATED TEST SUITE (STRICT TARGETS)          ")
    print("=" * 60)

    all_success = True
    for map_path in TARGETS.keys():
        print("-" * 50)
        success = run_test(map_path)
        if not success:
            all_success = False

    print("=" * 60)
    if all_success:
        print("  \033[92mALL TESTS PASSED PERFECTLY WITHIN SUBJECT TARGETS!\033[0m")
        sys.exit(0)
    else:
        print("  \033[91mSOME TESTS FAILED THE SUBJECT TARGETS. CHECK ABOVE!\033[0m")
        sys.exit(1)


if __name__ == "__main__":
    main()