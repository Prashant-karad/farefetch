---
title: Why your SQL query is slow: indexes explained with real timings
publisher: code-dojo
price: 350
license: lic_read_24h
---
We loaded five million orders into PostgreSQL and searched for one customer's orders. Without an index the database read every row, taking 820 milliseconds. After adding an index on customer_id the same query took 0.4 milliseconds. Indexes are not free: each one slowed inserts by about eight percent in our test and used extra disk space. A composite index on customer_id and created_at made the common query 'latest orders for a customer' fast without a separate sort. Use EXPLAIN ANALYZE to confirm the database actually uses your index.
