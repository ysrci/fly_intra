import sys
from parser import MapParser, ParseError
from pathfinder import MultiPathFinder
from simulator import Simulation


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 main.py <mapfile>")
        return
    mapfile = sys.argv[1]
    parse_map = MapParser()
    nb, start, end, graph = parse_map.parse_file(mapfile)

    finder = MultiPathFinder(graph)
    alloc = finder.drone_waste(start, end, nb)
    if not alloc.assignments:
        print("No valid path")
        return

    sim = Simulation(graph, alloc.assignments)
    turns = sim.run()

    print(f"\n\nNumber of turns: {alloc.nb_turns}\n\n")
    print(sim.format_turns(turns))


if __name__ == "__main__":
    try:
        main()
    except ParseError as e:
        print(e)
