"""
J-Graph (Justified Graph) space syntax analysis.

Algorithms based on Space Syntax theory:
  - BFS from each node computes Total Depth (TD)
  - Mean Depth (MD) = TD / (N - 1)
  - Relative Asymmetry (RA) = 2 * (MD - 1) / (N - 2)
  - Real Relative Asymmetry (RRA) = RA / D(N)
    where D(N) = 2 * ((log2((N+2)/3) - 1) * N + 1) / ((N-1) * (N-2))
  - Integration = 1 / RRA

Reference: Hillier, B., Hanson, J. and Graham, H. (1987). Ideas are in things: an
application of the space syntax method to discovering house genotypes. Environment
and Planning B: planning and design, 14(4), pp.363-385.
"""

import math
from collections import deque


def build_graph(node_ids, edge_pairs):
    """
    Build an adjacency list from node IDs and (from_id, to_id) edge pairs.

    Returns:
        dict: { node_id: [neighbor_id, ...] }
    """
    graph = {nid: [] for nid in node_ids}
    for a, b in edge_pairs:
        if a in graph and b in graph and a != b:
            if b not in graph[a]:
                graph[a].append(b)
            if a not in graph[b]:
                graph[b].append(a)
    return graph


def bfs_depth(graph, start):
    """
    BFS from `start`. Returns (total_depth, node_count) over all reachable nodes
    (excluding the start node itself from node_count but including depth sum to it as 0).

    total_depth = sum of distances from start to all other reachable nodes
    node_count  = number of reachable nodes including start
    """
    visited = {start: 0}
    queue = deque([start])
    total_depth = 0
    node_count = 1

    while queue:
        current = queue.popleft()
        current_depth = visited[current]
        for neighbor in graph[current]:
            if neighbor not in visited:
                d = current_depth + 1
                visited[neighbor] = d
                total_depth += d
                node_count += 1
                queue.append(neighbor)

    return total_depth, node_count


def _d_value(n):
    """
    Normalization constant D(N) from Hillier, Hanson & Graham (1987).
    For N <= 2, returns None (undefined).
    """
    if n <= 2:
        return None
    log_val = math.log2((n + 2) / 3.0)
    return 2.0 * ((log_val - 1.0) * n + 1.0) / ((n - 1) * (n - 2))


def calculate_integration(total_depth, node_count):
    """
    Given TD and N (node_count reachable from a root, including root),
    compute: MD, RA, RRA, Integration.

    Returns dict with keys: total_depth, node_count, mean_depth, ra, rra, integration
    All values are float or None if undefined.
    """
    n = node_count
    td = total_depth

    result = {
        "total_depth": td,
        "node_count": n,
        "mean_depth": None,
        "ra": None,
        "rra": None,
        "integration": None,
    }

    if n < 2:
        return result

    md = td / (n - 1)
    result["mean_depth"] = md

    if n < 3:
        return result

    ra = 2.0 * (md - 1.0) / (n - 2)
    result["ra"] = ra

    d = _d_value(n)
    if d is None or d == 0:
        return result

    rra = ra / d
    result["rra"] = rra

    if rra != 0:
        result["integration"] = 1.0 / rra

    return result


def run_analysis(node_ids, edge_pairs):
    """
    Run full j-graph analysis for all nodes.

    Args:
        node_ids: iterable of node identifiers
        edge_pairs: iterable of (id_a, id_b) tuples (undirected edges)

    Returns:
        dict: { node_id: { total_depth, node_count, mean_depth, ra, rra, integration } }
    """
    node_ids = list(node_ids)
    graph = build_graph(node_ids, edge_pairs)
    results = {}
    for nid in node_ids:
        td, nc = bfs_depth(graph, nid)
        results[nid] = calculate_integration(td, nc)
    return results


def match_line_endpoints_to_nodes(node_geometries, line_geometries, tolerance=1e-6):
    """
    For each line, find which nodes its start/end points snap to (within tolerance).

    Args:
        node_geometries: dict { node_id: QgsPointXY or (x, y) }
        line_geometries: dict { line_id: list of (x, y) or QgsPolylineXY }
        tolerance: snapping distance

    Returns:
        list of (node_id_a, node_id_b) edge pairs
    """
    def snap(px, py):
        best = None
        best_d = float("inf")
        for nid, geom in node_geometries.items():
            try:
                nx, ny = geom.x(), geom.y()
            except AttributeError:
                nx, ny = geom[0], geom[1]
            d = math.hypot(px - nx, py - ny)
            if d < best_d:
                best_d = d
                best = nid
        if best_d <= tolerance:
            return best
        return None

    edges = []
    for _lid, vertices in line_geometries.items():
        if not vertices:
            continue
        try:
            start = vertices[0]
            end = vertices[-1]
            sx, sy = start.x(), start.y()
            ex, ey = end.x(), end.y()
        except AttributeError:
            sx, sy = vertices[0]
            ex, ey = vertices[-1]

        a = snap(sx, sy)
        b = snap(ex, ey)
        if a is not None and b is not None and a != b:
            edges.append((a, b))

    return edges
