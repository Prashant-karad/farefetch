---
title: Find the slow part first: Python profiling in 10 minutes
publisher: code-dojo
price: 300
license: lic_read_24h
---
Most slow programs spend almost all of their time in one or two places, so guessing wastes effort. Start with cProfile: run python -m cProfile -s cumtime your_script.py and read the top ten lines of the report. In our test project, a single JSON parsing function used 71 percent of the total time, and fixing it made the whole program three times faster. For line-by-line detail, line_profiler shows exactly which line inside a function is expensive. For programs that are already running in production, py-spy can sample a live process without restarting it. Profile again after every change, because removing one bottleneck usually reveals the next one.
