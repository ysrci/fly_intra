import sys
from parser import MapParser
from solve import PathFinder, Scheduler, Simulator

def main():
    if len(sys.argv) != 2:
        print("Usage: python debug_print.py <map_file>")
        return

    # 1. Load the map
    flight_map = MapParser.load_file(sys.argv[1])
    
    # 2. Solve and simulate
    finder = PathFinder(flight_map)
    pool = finder.diverse_paths(max_paths=max(2, min(flight_map.nb_drones, len(flight_map.zones))))
    if not pool:
        pool = finder.disjoint_paths(max_paths=1)
        
    assignments = Scheduler(pool).assign(flight_map.nb_drones)
    frames = Simulator(flight_map).run(pool, assignments)
    
    # 3. Print everything clearly for copying
    print("\n=== COPY EVERYTHING BELOW THIS LINE ===\n")
    print(f"Total Turns Simulated: {len(frames)}")
    print("-" * 40)
    
    for idx, frame in enumerate(frames):
        # frame.turn shows the number, frame.moves is the list of movements
        moves_str = " | ".join(frame.moves) if frame.moves else "No drone moves (Idle Turn)"
        print(f"Turn {idx + 1}: {moves_str}")
        
    print("\n=== END OF COPY ===")

if __name__ == "__main__":
    main()
