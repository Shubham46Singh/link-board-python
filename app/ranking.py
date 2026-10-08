"""Pure ranking and comment-tree maths. No database, no HTTP.

PART ONE: THE FRONT PAGE.

Sorting by votes gives you a front page that never changes, because the post
at the top has been collecting votes since yesterday and the new one has not.
A hot ranking fixes that by trading votes against age. Two famous ones are
here, and they answer the brief's question differently.

    Reddit  sign(s) * log10(max(|s|, 1))  +  (created_at - EPOCH) / 45000
    HN      (points - 1) / (age_hours + 2) ** 1.8

The brief asks: how does a brand new post with one vote compare to a
day-old post with fifty?

    Reddit   new:  log10(1) = 0,         penalty 0           ->  t/45000 + 0.000
             old:  log10(50) = 1.699,    penalty 86400/45000 ->  t/45000 - 0.221
             The new post wins.

    HN       new:  (1-1) / 2^1.8                             ->  0.000
             old:  (50-1) / 26^1.8                           ->  0.139
             The day-old post wins.

Neither is wrong. They encode different opinions about what a front page is
for. HN's formula gives a single upvote literally nothing, so a new post
cannot move at all until two people like it; Reddit's gives a new post a free
ride for the first few hours. THE APP USES REDDIT'S, and you should be able
to say why in your README - and what it costs you.

The 45000 is the whole formula. It is the number of seconds of age worth one
order of magnitude of votes: 12.5 hours. Ten times the votes buys 12.5 hours
of staying power, a hundred times buys 25 hours, and no amount of votes buys
a third day. `age_worth_of` works that out for any multiplier.

STABILITY. Reddit's score does not contain "now" at all - only the post's own
creation time. So the gap between any two posts is fixed the moment they are
both submitted, and their relative order can never change unless somebody
votes. The whole page slides down together. That is why it can live in a
Redis sorted set and be rescored lazily instead of on every request.
`is_order_stable` checks that property. It is True for Reddit's formula for
any two posts and any two moments. It is not for HN's: a post on 5 points
posted now sits above one on 50 points posted ten hours ago, and forty-eight
hours later, with not one vote cast in between, they have swapped. Write
that test - it is the one that shows `is_order_stable` can actually fail.

PART TWO: COMMENT TREES.

Comments arrive as a flat table of (id, parent_id). Turning that into a
nested thread is the other half of the assignment, and the catch is doing it
without a recursive Python function. `thread_order` walks the tree with an
explicit stack, and `nest` builds the nested shape in two flat passes over
rows that are already in display order - which is exactly what a single
`WITH RECURSIVE` query hands you. Both of them have to survive the data
being wrong: a comment whose parent was deleted (an orphan), and a comment
that is its own ancestor (a cycle), which will hang any implementation that
assumes the input is a tree.

Worked testing: the two formulas disagreeing on the brief's own question;
the Reddit score of a post with zero votes, and one more downvotes than up;
`age_worth_of(10)` being 45000; `is_order_stable` True for Reddit and False
for HN; `nest` on an empty list, a flat list with no parents, a single deep
chain, and a list whose parents come after their children; `thread_order` on
a two-node cycle and on an orphan; and that `find_cycles` names the right
ids.
"""
import math

REDDIT_EPOCH = 1134028003   # 2005-12-08, the day reddit started counting
DECAY_SECONDS = 45000       # 12.5 hours == one order of magnitude of votes
HN_GRAVITY = 1.8
DEFAULT_FORMULA = "reddit"


class RankingError(ValueError):
    pass


# --------------------------------------------------------------------------
# the hot formulas
# --------------------------------------------------------------------------

def net_score(ups, downs=0):
    return int(ups) - int(downs)


def hot(ups, downs, created_epoch, epoch=REDDIT_EPOCH, decay=DECAY_SECONDS):
    """Reddit's hot ranking.

    Note what it does NOT take: the current time. The score of a post is
    fixed by its votes and its birthday, so two posts keep their relative
    order forever unless one of them gets a vote.
    """
    if decay <= 0:
        raise RankingError("the decay constant must be positive")
    s = net_score(ups, downs)
    order = math.log10(max(abs(s), 1))
    sign = 1 if s > 0 else (-1 if s < 0 else 0)
    return round(sign * order + (float(created_epoch) - epoch) / float(decay), 7)


def hn_hot(ups, downs, created_epoch, now, gravity=HN_GRAVITY):
    """Hacker News' ranking. Needs `now`, which is the interesting difference.

    A post with one upvote scores exactly zero, forever. That is deliberate
    over there, and it is the opposite of the choice this app makes.
    """
    points = net_score(ups, downs)
    age_hours = max(0.0, (float(now) - float(created_epoch)) / 3600.0)
    return round(max(0, points - 1) / ((age_hours + 2.0) ** gravity), 7)


FORMULAS = {"reddit": "hot", "hn": "hn_hot"}


def score(post, now=None, formula=DEFAULT_FORMULA):
    """One post's hot score. `post` needs ups, downs and created_epoch."""
    f = str(formula).lower()
    if f not in FORMULAS:
        raise RankingError(f"unknown formula {formula!r} - have {sorted(FORMULAS)}")
    ups = post.get("ups", 0)
    downs = post.get("downs", 0)
    born = post.get("created_epoch")
    if born is None:
        raise RankingError("a post needs created_epoch")
    if f == "reddit":
        return hot(ups, downs, born)
    if now is None:
        raise RankingError("the HN formula needs the current time")
    return hn_hot(ups, downs, born, now)


def age_worth_of(vote_multiplier, decay=DECAY_SECONDS):
    """How many seconds of age one multiple of votes buys you.

    age_worth_of(10) is 45000 - ten times the votes is worth 12.5 hours.
    age_worth_of(2) is about 13548 - doubling your votes buys under 4 hours.
    """
    m = float(vote_multiplier)
    if m <= 0:
        raise RankingError("the multiplier must be positive")
    return round(math.log10(m) * decay, 2)


def rank(posts, now=None, formula=DEFAULT_FORMULA):
    """The front page: every post scored and sorted, highest first.

    Ties break on the newer post, then on id, so the order is total and the
    same input always gives the same page.
    """
    scored = []
    for p in posts:
        scored.append({**p, "hot": score(p, now, formula)})
    scored.sort(key=lambda p: (-p["hot"], -float(p.get("created_epoch", 0)),
                               str(p.get("id", ""))))
    for i, p in enumerate(scored, start=1):
        p["position"] = i
    return scored


def is_order_stable(posts, t1, t2, formula=DEFAULT_FORMULA):
    """Does the page order stay the same between two moments, with no votes?

    True for Reddit's formula at any two times, because `now` is not in it.
    False for HN's, where every post decays at its own rate and they overtake
    each other while nobody is doing anything.
    """
    a = [p.get("id") for p in rank(posts, t1, formula)]
    b = [p.get("id") for p in rank(posts, t2, formula)]
    return a == b


def explain(a, b, now):
    """Why one post is above another, under both formulas."""
    out = {"now": float(now), "formulas": {}}
    for f in ("reddit", "hn"):
        sa, sb = score(a, now, f), score(b, now, f)
        out["formulas"][f] = {
            "a": sa, "b": sb,
            "winner": "a" if sa > sb else ("b" if sb > sa else "tie"),
            "margin": round(abs(sa - sb), 7)}
    verdicts = {v["winner"] for v in out["formulas"].values()}
    out["agree"] = len(verdicts) == 1
    return out


# --------------------------------------------------------------------------
# comment trees
# --------------------------------------------------------------------------

def _roots_and_children(rows, id_key="id", parent_key="parent_id"):
    ids = {r[id_key] for r in rows}
    children, roots = {}, []
    for r in rows:
        pid = r.get(parent_key)
        # A comment whose parent is missing (deleted, or on another link) is
        # an orphan, and a comment that is its own parent is nonsense. Both
        # get promoted to the top rather than disappearing.
        if pid is None or pid not in ids or pid == r[id_key]:
            roots.append(r[id_key])
        else:
            children.setdefault(pid, []).append(r[id_key])
    for k in children:
        children[k].sort()
    roots.sort()
    return roots, children


def thread_order(rows, id_key="id", parent_key="parent_id", max_depth=None):
    """Flat list of (id, parent_id, ...) -> display order, with a depth.

    Depth-first, oldest sibling first, using an explicit stack. No recursion,
    so a thread 50,000 deep is a long loop rather than a stack overflow - and
    a cycle is a terminating loop rather than a hang.

    This is the reference implementation of what a `WITH RECURSIVE` query
    ordered by its path array returns. Write a test that runs both over the
    same rows and asserts they match, and you have tested the SQL.
    """
    by_id = {r[id_key]: r for r in rows}
    roots, children = _roots_and_children(rows, id_key, parent_key)
    out, seen = [], set()
    stack = [(i, 1) for i in reversed(roots)]
    while stack:
        cid, depth = stack.pop()
        if cid in seen:
            continue
        seen.add(cid)
        node = dict(by_id[cid])
        node["depth"] = depth
        if max_depth is not None and depth > max_depth:
            node["collapsed"] = True
        out.append(node)
        for kid in reversed(children.get(cid, [])):
            if kid not in seen:
                stack.append((kid, depth + 1))
    # Whatever the walk could not reach is inside a cycle. Show it anyway,
    # flagged, rather than silently losing somebody's comment.
    for r in rows:
        if r[id_key] not in seen:
            out.append({**r, "depth": 1, "unreachable": True})
    return out


def nest(rows, id_key="id", parent_key="parent_id", children_key="replies"):
    """Flat rows -> nested tree, in two passes and no recursion.

    This is what you run over the rows a single recursive SQL query gave you:
    the database did the walking, this only reassembles the shape. Rows in
    any order work, including children before their parents.
    """
    index = {}
    for r in rows:
        index[r[id_key]] = {**r, children_key: []}
    roots = []
    for r in rows:
        node = index[r[id_key]]
        pid = r.get(parent_key)
        parent = index.get(pid) if pid is not None else None
        if parent is None or parent is node:
            roots.append(node)
        else:
            parent[children_key].append(node)
    # Nodes in a cycle are nobody's root and would vanish. Lift them out.
    placed = set()
    stack = list(roots)
    while stack:
        n = stack.pop()
        if n[id_key] in placed:
            continue
        placed.add(n[id_key])
        stack.extend(n[children_key])
    for r in rows:
        if r[id_key] not in placed:
            node = index[r[id_key]]
            node["unreachable"] = True
            roots.append(node)
            placed.add(r[id_key])
    return roots


def flatten(tree, children_key="replies", depth=1):
    """Nested tree -> flat list with depths. Iterative, for the same reason."""
    out = []
    stack = [(n, depth) for n in reversed(tree)]
    while stack:
        node, d = stack.pop()
        flat = {k: v for k, v in node.items() if k != children_key}
        flat["depth"] = d
        out.append(flat)
        for child in reversed(node.get(children_key, [])):
            stack.append((child, d + 1))
    return out


def find_cycles(rows, id_key="id", parent_key="parent_id"):
    """Ids that are their own ancestor. Walk up from each node with a visited
    set - O(n) overall because settled nodes are remembered."""
    parent = {r[id_key]: r.get(parent_key) for r in rows}
    settled, bad = set(), set()
    for start in parent:
        if start in settled:
            continue
        path, cur = [], start
        on_path = set()
        while cur is not None and cur in parent and cur not in settled:
            if cur in on_path:
                i = path.index(cur)
                bad.update(path[i:])
                break
            path.append(cur)
            on_path.add(cur)
            cur = parent[cur]
        settled.update(path)
    return sorted(bad, key=str)


def tree_stats(rows, id_key="id", parent_key="parent_id"):
    """Numbers worth putting next to a thread."""
    ordered = thread_order(rows, id_key, parent_key)
    roots, _ = _roots_and_children(rows, id_key, parent_key)
    ids = {r[id_key] for r in rows}
    return {"comments": len(rows),
            "top_level": len(roots),
            "max_depth": max([n["depth"] for n in ordered], default=0),
            "orphans": sorted([r[id_key] for r in rows
                               if r.get(parent_key) is not None
                               and r.get(parent_key) not in ids], key=str),
            "cycles": find_cycles(rows, id_key, parent_key)}
