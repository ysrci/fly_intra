import sys
from parser import MapParser, ParseError
from solve import PathFinder, Scheduler, Simulator


def get_best_plan(flight_map) -> tuple[list, list, list] | None:
    finder = PathFinder(flight_map)
    budget = max(2, min(flight_map.nb_drones, len(flight_map.zones)))
    
    # Gather both path pools
    pools = [
        finder.disjoint_paths(max_paths=budget),
        finder.diverse_paths(max_paths=budget),
    ]
    
    seen = set()
    best = None
    
    # Simulate all possible subsets to find the one with minimum turns
    for pool in pools:
        for k in range(1, len(pool) + 1):
            subset = pool[:k]
            key = tuple(p.zones for p in subset)
            if key in seen:
                continue
            seen.add(key)
            
            try:
                assignments = Scheduler(subset).assign(flight_map.nb_drones)
                simulator = Simulator(flight_map)
                frames = simulator.run(subset, assignments)
                
                active_turns = sum(1 for frame in frames if frame.moves)
                
                if best is None or active_turns < best[3]:
                    best = (subset, assignments, frames, active_turns)
            except Exception:
                continue
                
    if best is None:
        return None
    return best[0], best[1], best[2]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 main.py <map_file.txt>")
        sys.exit(1)

    map_path = sys.argv[1]

    try:
        # 1. Parsing Phase
        flight_map = MapParser.load_file(map_path)

        # 2. Optimization and Simulation Phase
        plan = get_best_plan(flight_map)
        if plan is None:
            print("Error: No paths available to schedule.", file=sys.stderr)
            sys.exit(1)
            
        paths, assignments, frames = plan

        # 3. Output Results
        total_turns = 0
        for frame in frames:
            if frame.moves:
                print(" ".join(frame.moves))
                total_turns += 1
        
        print("---")
        print(f"Total Simulation Turns: {total_turns}")

    except ParseError as pe:
        print(f"Error parsing map: {pe}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Execution error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
