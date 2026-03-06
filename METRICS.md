# J-Graph Analysis — Metrics Reference

Based on: Hillier, B., Hanson, J. and Graham, H. (1987). Ideas are in things: an application
of the space syntax method to discovering house genotypes. *Environment and Planning B:
planning and design*, 14(4), pp.363–385.

---

## Base Node (Root)

The **base node** is the starting point of the justified graph — typically representing
"outside" or the main entrance of a building. All depth values are measured relative to it.

---

## Output Fields

### `jg_depth` — Depth from Base Node

The number of **topological steps** from the base node to this node, counted along graph edges.

| Value | Meaning |
|-------|---------|
| 0     | This node IS the base node |
| 1     | Directly connected to base |
| 2     | One node away from base |
| NULL  | Not reachable from base (disconnected component) |

This is the primary metric of the **justified graph**: nodes are visually stacked in rows
by their depth level, revealing the hierarchical structure of the layout.

---

### `jg_td` — Total Depth (global)

The sum of shortest-path distances from this node to **every other node** in the graph.

```
TD(i) = sum of d(i, j) for all j ≠ i
```

A low TD means a node is "close" to all other spaces — a good candidate for a gathering
point or a highly integrated space.

---

### `jg_nc` — Connected Node Count

The number of nodes reachable from this node (including itself), found by BFS traversal.

In a fully connected graph this equals the total node count. A lower value indicates
the node belongs to a **disconnected sub-graph**.

---

### `jg_md` — Mean Depth

The average topological distance from this node to all other reachable nodes.

```
MD(i) = TD(i) / (N - 1)
```

where `N` = `jg_nc` (reachable node count).

Interpretation: lower MD = more central/accessible node.

---

### `jg_ra` — Relative Asymmetry

Normalises Mean Depth against graph size so nodes in graphs of different sizes
can be compared.

```
RA(i) = 2 * (MD(i) - 1) / (N - 2)
```

Range: 0 (maximum integration) to 1 (maximum segregation).

---

### `jg_rra` — Real Relative Asymmetry

Further normalises RA against a theoretical baseline `D(N)` derived from a
**diamond-shaped** reference graph (the most integrated possible topology for N nodes),
as defined in Hillier, Hanson & Graham (1987).
This makes integration values comparable across buildings/layouts of different sizes.

```
RRA(i) = RA(i) / D(N)

D(N) = 2 * ((log₂((N+2)/3) - 1) * N + 1) / ((N-1) * (N-2))
```

---

### `jg_int` — Integration

The primary Space Syntax metric. The inverse of RRA.

```
Integration(i) = 1 / RRA(i)
```

| Value | Meaning |
|-------|---------|
| High  | Node is well-integrated — easy to reach from anywhere |
| Low   | Node is segregated — hard to reach |
| NULL  | Undefined (graph too small, or node perfectly integrated with RRA=0) |

**Typical use:** colour-map nodes by `jg_int` to identify the most accessible spaces
in a building or urban block (a "heat map" of movement potential).

---

## Relationships Between Metrics

```
jg_depth  ← rooted at your chosen base node (local perspective)
jg_td     ← sum of all distances from this node (global perspective)
jg_md     ← td / (N-1)
jg_ra     ← normalised md
jg_rra    ← size-normalised ra
jg_int    ← 1 / rra  (the headline metric)
```

---

## References

- Hillier, B., Hanson, J. and Graham, H. (1987). Ideas are in things: an application of the space syntax method to discovering house genotypes. *Environment and Planning B: planning and design*, 14(4), pp.363–385.

## Repository

https://github.com/HdMiii/SS_Jgraph

## Author

deminhu — demin.hu.22@ucl.ac.uk
