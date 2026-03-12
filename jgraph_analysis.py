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


def run_analysis(node_ids, edge_pairs, graph=None):
    """
    Run full j-graph analysis for all nodes.

    Args:
        node_ids: iterable of node identifiers
        edge_pairs: iterable of (id_a, id_b) tuples (undirected edges)
        graph: optional pre-built adjacency dict; built from node_ids/edge_pairs if None

    Returns:
        dict: { node_id: { total_depth, node_count, mean_depth, ra, rra, integration } }
    """
    node_ids = list(node_ids)
    if graph is None:
        graph = build_graph(node_ids, edge_pairs)
    results = {}
    for nid in node_ids:
        td, nc = bfs_depth(graph, nid)
        results[nid] = calculate_integration(td, nc)
    return results


def compute_jgraph_layout(graph, depth_from_root, node_spacing=1.0, level_spacing=1.0, origin=(0.0, 0.0)):
    """
    Compute (x, y) positions for a classic justified graph layout.

    - Base node (depth 0) is placed at `origin` (default: 0, 0).
      Pass the base node's real geographic coordinates to anchor the diagram there.
    - Each successive depth level is placed one level_spacing unit higher.
    - Nodes within a level are spread horizontally (centred around origin x),
      sorted by their BFS-tree parent's x position so children appear
      directly above their parent.

    Args:
        graph:           adjacency dict { node_id: [neighbor_id, ...] }
        depth_from_root: dict { node_id: depth (int) or None if unreachable }
        node_spacing:    horizontal distance between nodes at the same level
        level_spacing:   vertical distance between depth levels
        origin:          (x, y) of the base node (depth 0)

    Returns:
        dict { node_id: (x, y) } — only reachable nodes are included
    """
    # Group reachable nodes by depth
    levels = {}
    for node_id, depth in depth_from_root.items():
        if depth is None:
            continue
        levels.setdefault(depth, []).append(node_id)

    if not levels:
        return {}

    # Build BFS-tree parent map: for each node, find the neighbour one level up
    parent = {}
    for node_id, depth in depth_from_root.items():
        if depth is None or depth == 0:
            continue
        for neighbor in graph[node_id]:
            if depth_from_root.get(neighbor) == depth - 1:
                parent[node_id] = neighbor
                break

    positions = {}
    max_depth = max(levels.keys())
    ox, oy = origin

    # Place root at the real origin (base node's geographic location)
    for node_id in levels.get(0, []):
        positions[node_id] = (ox, oy)

    # Place each level above the previous
    for depth in range(1, max_depth + 1):
        nodes = levels.get(depth, [])
        if not nodes:
            continue
        # Sort by parent x so children cluster under their parent
        nodes.sort(key=lambda n: positions.get(parent.get(n), (ox, oy))[0])
        n = len(nodes)
        for i, node_id in enumerate(nodes):
            x = ox + (i - (n - 1) / 2.0) * node_spacing
            y = oy + depth * level_spacing
            positions[node_id] = (x, y)

    return positions


def compute_radial_layout(graph, depth_from_root, ring_spacing=1.0, origin=(0.0, 0.0)):
    """
    Compute (x, y) positions for a radial justified graph layout.

    - Base node (depth 0) is placed at `origin`.
    - Each successive depth level forms a concentric ring at radius = depth * ring_spacing.
    - Depth-1 nodes are evenly spaced around the full circle (e.g. 3 nodes = 120° each).
    - Deeper nodes stay within their depth-1 ancestor's angular sector,
      subdivided proportionally by subtree leaf count so branches are visually distinct.

    Args:
        graph:           adjacency dict { node_id: [neighbor_id, ...] }
        depth_from_root: dict { node_id: depth (int) or None if unreachable }
        ring_spacing:    radial distance between concentric depth rings
        origin:          (x, y) of the base node (depth 0)

    Returns:
        dict { node_id: (x, y) } — only reachable nodes are included
    """
    # Group reachable nodes by depth
    levels = {}
    for node_id, depth in depth_from_root.items():
        if depth is None:
            continue
        levels.setdefault(depth, []).append(node_id)

    if not levels:
        return {}

    # Build BFS-tree parent map and children map
    parent = {}
    children = {}
    for node_id, depth in depth_from_root.items():
        if depth is None or depth == 0:
            continue
        for neighbor in graph[node_id]:
            if depth_from_root.get(neighbor) == depth - 1:
                parent[node_id] = neighbor
                children.setdefault(neighbor, []).append(node_id)
                break

    max_depth = max(levels.keys())

    # Memoized leaf count for proportional angular allocation
    _leaf_cache = {}

    def leaf_count(node):
        if node in _leaf_cache:
            return _leaf_cache[node]
        kids = children.get(node, [])
        if not kids:
            result = 1
        else:
            result = sum(leaf_count(c) for c in kids)
        _leaf_cache[node] = result
        return result

    positions = {}
    ox, oy = origin

    # Place root at origin
    for node_id in levels.get(0, []):
        positions[node_id] = (ox, oy)

    if max_depth == 0:
        return positions

    # sectors[node_id] = (angle_start, angle_end)
    sectors = {}

    # Depth 1: equal angular sectors
    depth1_nodes = levels.get(1, [])
    n1 = len(depth1_nodes)
    if n1 == 0:
        return positions

    sector_sweep = 2.0 * math.pi / n1
    for i, node_id in enumerate(depth1_nodes):
        a_start = i * sector_sweep
        a_end = a_start + sector_sweep
        sectors[node_id] = (a_start, a_end)
        angle_mid = (a_start + a_end) / 2.0
        x = ox + ring_spacing * math.cos(angle_mid)
        y = oy + ring_spacing * math.sin(angle_mid)
        positions[node_id] = (x, y)

    # Depth 2+: subdivide parent's sector proportionally by leaf count
    for depth in range(2, max_depth + 1):
        nodes = levels.get(depth, [])
        if not nodes:
            continue
        radius = depth * ring_spacing

        # Group nodes by parent to subdivide each parent's sector
        by_parent = {}
        for node_id in nodes:
            p = parent.get(node_id)
            by_parent.setdefault(p, []).append(node_id)

        for p, kids in by_parent.items():
            p_start, p_end = sectors.get(p, (0.0, 2.0 * math.pi))
            total_leaves = sum(leaf_count(c) for c in kids)
            if total_leaves == 0:
                continue

            sub_angle = p_start
            for child in kids:
                lc = leaf_count(child)
                sweep = (p_end - p_start) * lc / total_leaves
                c_start = sub_angle
                c_end = sub_angle + sweep
                sectors[child] = (c_start, c_end)

                angle_mid = (c_start + c_end) / 2.0
                x = ox + radius * math.cos(angle_mid)
                y = oy + radius * math.sin(angle_mid)
                positions[child] = (x, y)
                sub_angle += sweep

    return positions


def match_line_endpoints_to_nodes(node_geometries, line_geometries, tolerance=1e-6):
    """
    For each line, find which nodes its start/end points snap to (within tolerance).

    Args:
        node_geometries: dict { node_id: QgsPointXY or (x, y) }
        line_geometries: dict { line_id: list of (x, y) or QgsPolylineXY }
        tolerance: snapping distance

    Returns:
        list of (node_id_a, node_id_b, line_id) triples
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

    def _vertex_coords(v):
        try:
            return v.x(), v.y()
        except AttributeError:
            return v[0], v[1]

    edges = []
    for lid, vertices in line_geometries.items():
        if len(vertices) < 2:
            continue
        # Treat each segment of the polyline as a potential edge
        for i in range(len(vertices) - 1):
            sx, sy = _vertex_coords(vertices[i])
            ex, ey = _vertex_coords(vertices[i + 1])
            a = snap(sx, sy)
            b = snap(ex, ey)
            if a is not None and b is not None and a != b:
                edges.append((a, b, lid))

    return edges
