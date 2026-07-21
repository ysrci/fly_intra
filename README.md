_This project has been created as part of the 42 curriculum by yel-bakk_


# Description

Fly-in is a python project that simulaes drones moving inside a map.

The goal of the projet is to find good paths from start hub to the end hub and move all drones in the smallest number of turns, The program reads a map file, checks that it is valid, finds paths, assigns paths to drones, and runs the simulation.

The project is divided into small parts: map parsing, path finding, simulation, and visualization.

---

# Instructions

## Requirements
* Python 3.10 or later
* Install the required packages
```bash
make install
```

## Run the program
```bash
make run
```

__To use another map__
```bash
make run MAP=maps/easy/02_simple_fork.txt
```

## Code check
__Run flake8 and mypy__
```bash
make lint
```

## Clean
__Remove cache files__
```bash
make clean
```

---

# Resources

* Pygame:
https://www.pygame.org/docs/
https://youtu.be/FfWpgLFMI7w?si=QJCQvD-cuqwBAUKK
https://www.geeksforgeeks.org/python/pygame-tutorial/

* heapq:
https://youtu.be/E2v9hBgG6gE?si=ifov17Z3LSkqz8w6

* re:
https://youtu.be/K8L6KVGG-7o?si=1EINCQPZ9AoxkF2_

* dataclasses
https://youtu.be/5mMpM8zK4pY?si=JtlYP82s67V4ELhJ
https://youtu.be/vCLetdhswMg?si=f4EYDqriY3zeu0TP

* typing
https://youtu.be/QORvB-_mbZ0?si=IDjqA-aiFZTwjRWX

### Ai Usage
__Help me understand and fix maypy erros__
__Improve the algorithm__

