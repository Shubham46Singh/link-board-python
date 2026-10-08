-- These ages and vote counts are chosen, not random. Link 4 is two minutes
-- old with a single upvote; link 5 is a day old with fifty. Under this app's
-- ranking the two-minute-old post with one vote is ABOVE the day-old post
-- with fifty, which is the brief's question answered by the front page
-- itself. Hit /ranking/explain?a=4&b=5 to see both formulas argue about it.
INSERT INTO links (id, title, url, submitted_by, ups, downs, created_at) VALUES
 (1, 'Postgres full-text search is underrated', 'https://example.edu/pg-fts', 'asha', 180, 4, now() - interval '2 days'),
 (2, 'A 400-line interpreter you can read in one sitting', 'https://example.edu/tiny-lisp', 'vikram', 402, 11, now() - interval '12 hours'),
 (3, 'Why your Docker build takes four minutes', 'https://example.edu/docker-cache', 'priya', 121, 3, now() - interval '6 hours'),
 (4, 'I rewrote the campus bus timetable as an API', 'https://example.edu/bus-api', 'rahul', 1, 0, now() - interval '2 minutes'),
 (5, 'Every CAP theorem explainer is wrong about the P', 'https://example.edu/cap-p', 'fatima', 50, 0, now() - interval '1 day'),
 (6, 'Ask: how do you revise for a viva?', 'https://example.edu/viva-help', 'dev', 9, 1, now() - interval '3 hours'),
 (7, 'The entire CS syllabus, ranked (bad opinions inside)', 'https://example.edu/ranked', 'troll', 2, 9, now() - interval '1 hour'),
 (8, 'Lecture notes: B-trees, with the pictures that actually help', 'https://example.edu/btrees', 'meera', 2100, 30, now() - interval '5 days'),
 (9, 'Our hostel wifi graphed for 30 days', 'https://example.edu/wifi-graph', 'arjun', 64, 2, now() - interval '9 hours'),
 (10, 'Show: a Makefile that explains itself', 'https://example.edu/self-doc-make', 'nisha', 33, 1, now() - interval '4 hours')
ON CONFLICT (id) DO NOTHING;
SELECT setval('links_id_seq', GREATEST((SELECT MAX(id) FROM links), 1));

-- Link 2 carries a thread five levels deep with branches at every level, so
-- the recursive query has something real to walk. Ordering by the path array
-- is what puts comment 7 under comment 4 instead of at the bottom.
INSERT INTO comments (id, link_id, parent_id, body, author, created_at) VALUES
 (1, 2, NULL, 'The garbage collector chapter is where I stopped understanding anything.', 'asha', now() - interval '11 hours'),
 (2, 2, 1, 'Skip it on the first read. Mark-and-sweep in 20 lines is at the end of the file.', 'vikram', now() - interval '10 hours'),
 (3, 2, 2, 'This is the advice I needed three weeks ago.', 'asha', now() - interval '9 hours'),
 (4, 2, 2, 'Does it handle cycles though? Most toy collectors quietly do not.', 'priya', now() - interval '9 hours'),
 (5, 2, 4, 'It does. That is the whole point of mark-and-sweep over refcounting.', 'vikram', now() - interval '8 hours'),
 (6, 2, 5, 'Right, refcounting is the one that leaks on cycles. I had these backwards.', 'priya', now() - interval '8 hours'),
 (7, 2, 6, 'Everyone has these backwards once. It is a rite of passage.', 'meera', now() - interval '7 hours'),
 (8, 2, NULL, 'Ran it on the lab machines. 400 lines, zero dependencies, compiles in under a second.', 'dev', now() - interval '10 hours'),
 (9, 2, 8, 'What did you use to time it?', 'arjun', now() - interval '9 hours'),
 (10, 2, 9, 'hyperfine. It reruns until the numbers stop moving.', 'dev', now() - interval '8 hours'),
 (11, 2, NULL, 'Saving this for the compilers elective next semester.', 'nisha', now() - interval '6 hours'),
 (12, 1, NULL, 'tsvector plus a GIN index got our search from 900ms to 4ms. No extra service.', 'fatima', now() - interval '2 days'),
 (13, 1, 12, 'Did you need a trigger to keep the tsvector column in step?', 'rahul', now() - interval '1 day'),
 (14, 1, 13, 'Generated column. Postgres 12 and up does it for you.', 'fatima', now() - interval '1 day'),
 (15, 3, NULL, 'Putting COPY . . above the dependency install is the whole bug, every time.', 'asha', now() - interval '5 hours'),
 (16, 3, 15, 'Our CI went from 4 minutes to 20 seconds on exactly that one-line move.', 'priya', now() - interval '4 hours'),
 (17, 6, NULL, 'Say your answer out loud to an empty room. It is unbearable and it works.', 'meera', now() - interval '2 hours'),
 (18, 6, 17, 'Can confirm. My flatmate now knows more about B-trees than I do.', 'dev', now() - interval '1 hour')
ON CONFLICT (id) DO NOTHING;
SELECT setval('comments_id_seq', GREATEST((SELECT MAX(id) FROM comments), 1));
