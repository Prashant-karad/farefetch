---
title: We benchmarked 6 ways to speed up a slow Python loop
publisher: code-dojo
price: 400
license: lic_read_24h
---
We took one slow function, summing the squares of ten million numbers in a plain for loop, and rewrote it six ways on the same laptop. The plain loop took 1.9 seconds. Moving the work into a list comprehension brought it to 1.2 seconds. Using the built-in sum with a generator expression gave 1.1 seconds. Caching attribute lookups in local variables saved another ten percent. The big jumps came from changing tools: NumPy vectorised the whole calculation in 0.04 seconds, about 47 times faster than the loop, and compiling the same loop with Numba took 0.02 seconds after the first run. Multiprocessing on eight cores reached 0.35 seconds but added start-up overhead that made it slower than the loop for small inputs. Our rule of thumb from these numbers: measure first, then reach for NumPy when the work is numeric, Numba when it is a tight custom loop, and multiprocessing only for large, independent chunks of work.
