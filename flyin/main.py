import sys

from parser import parse_file
from pathfinder import MultiPathFinder
from simulator import Simulation, format_turns


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 main.py <mapfile>")
        return
    mapfile = sys.argv[1]
    nb, start, end, graph = parse_file(mapfile)

    finder = MultiPathFinder(graph)
    alloc = finder.allocate_drones(start, end, nb)
    if not alloc.assignments:
        print("No valid path")
        return

    sim = Simulation(graph, alloc.assignments)
    turns = sim.run()

    print("Estimated turns:", alloc.estimated_turns)
    print("Actual turns:", len(turns))
    print(format_turns(turns))


if __name__ == "__main__":
    main()
