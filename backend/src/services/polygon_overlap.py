"""凸包面交叠/新增/减少面积，纯标准库实现。

只比较两凸包的二维面积：
- point/line 等退化凸包没有二维面，不参与面积交叠（点线、相切都不算重叠面）；
- polygon 之间用 Sutherland-Hodgman 凸多边形裁剪求交，交叠面积可能为 0（相离或仅相切）；
- 新增=复测凸包面积-交叠，减少=基准凸包面积-交叠；
- 交叠为 0 或裁剪结果退化（<3 顶点）时统一返回零面积空交，绝不把相切/点接触伪造成面。
"""
import math


def _polygon_area(vertices):
    """平移到首顶点后 shoelace，避免大绝对坐标乘积抵消；输入为 CCW 顶点列表。"""
    if len(vertices) < 3:
        return 0.0
    x0, y0 = vertices[0]
    local = [(x - x0, y - y0) for x, y in vertices]
    value = abs(math.fsum(
        local[i][0] * local[(i + 1) % len(local)][1]
        - local[(i + 1) % len(local)][0] * local[i][1]
        for i in range(len(local))
    )) / 2.0
    if not math.isfinite(value):
        raise ValueError('overlap area overflow')
    return value


def _line_side(p, a, b):
    """点 p 相对有向边 a->b 的叉积；>=0 视为在裁剪多边形内侧（CCW）。"""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _intersection(p, q, a, b):
    """线段 p-q 与裁剪边 a-b 的交点（参数化求交）。"""
    r = (q[0] - p[0], q[1] - p[1])
    s = (b[0] - a[0], b[1] - a[1])
    denom = r[0] * s[1] - r[1] * s[0]
    t = ((a[0] - p[0]) * s[1] - (a[1] - p[1]) * s[0]) / denom
    return (p[0] + t * r[0], p[1] + t * r[1])


def _clip(subject, clipping):
    """Sutherland-Hodgman：用 CCW 凸裁剪多边形 clipping 裁 subject。"""
    output = [tuple(p) for p in subject]
    cn = len(clipping)
    for i in range(cn):
        a = clipping[i]
        b = clipping[(i + 1) % cn]
        if not output:
            break
        inputs = output
        output = []
        prev = inputs[-1]
        prev_inside = _line_side(prev, a, b) >= 0.0
        for cur in inputs:
            cur_inside = _line_side(cur, a, b) >= 0.0
            if cur_inside:
                if not prev_inside:
                    output.append(_intersection(prev, cur, a, b))
                output.append(cur)
            elif prev_inside:
                output.append(_intersection(prev, cur, a, b))
            prev, prev_inside = cur, cur_inside
    return output


def _dedupe_collinear(vertices, eps):
    """去除裁剪产生的重复点与共线内点，保留真实角点；eps 为合并阈值（米）。"""
    if len(vertices) < 3:
        return []
    cleaned = []
    for p in vertices:
        if not cleaned or math.dist(p, cleaned[-1]) > eps:
            cleaned.append(p)
    if len(cleaned) > 1 and math.dist(cleaned[0], cleaned[-1]) <= eps:
        cleaned.pop()
    if len(cleaned) < 3:
        return []
    kept = []
    n = len(cleaned)
    for i in range(n):
        a, b, c = cleaned[(i - 1) % n], cleaned[i], cleaned[(i + 1) % n]
        if abs(_line_side(c, a, b)) > eps * max(1.0, math.dist(a, c)):
            kept.append(b)
    return kept if len(kept) >= 3 else []


def convex_overlap(baseline_vertices, retest_vertices, area_tolerance=1e-9):
    """计算两个 CCW 凸多边形的交叠面。

    返回 {'overlap_area','overlap_vertices'}。相离/相切/退化均返回 0 面积与空顶点。
    area_tolerance 是相对面积容差（乘以参考面积尺度），用于把数值噪声下的零交叠归零。
    """
    base = [tuple(p) for p in baseline_vertices]
    retest = [tuple(p) for p in retest_vertices]
    if len(base) < 3 or len(retest) < 3:
        return {'overlap_area': 0.0, 'overlap_vertices': []}
    raw = _clip(retest, base)
    if len(raw) < 3:
        return {'overlap_area': 0.0, 'overlap_vertices': []}
    scale = max(
        (max(x for x, _ in base) - min(x for x, _ in base)),
        (max(y for _, y in base) - min(y for _, y in base)),
        (max(x for x, _ in retest) - min(x for x, _ in retest)),
        (max(y for _, y in retest) - min(y for _, y in retest)),
        1.0,
    )
    eps = 1e-10 * scale
    overlap_polygon = _dedupe_collinear(raw, eps)
    area = _polygon_area(overlap_polygon) if overlap_polygon else 0.0
    floor = area_tolerance * max(1.0, _polygon_area(base), _polygon_area(retest))
    if area <= floor:
        # 数值噪声下的相切/点接触/线接触：没有可计的二维交叠面。
        return {'overlap_area': 0.0, 'overlap_vertices': []}
    return {
        'overlap_area': area,
        'overlap_vertices': [list(p) for p in overlap_polygon],
    }
