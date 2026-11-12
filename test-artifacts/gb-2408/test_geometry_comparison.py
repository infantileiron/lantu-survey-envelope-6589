"""复测比较几何与守恒的独立测试（纯标准库，不依赖 MySQL/Redis/Shapely）。

运行：python3 -I test_geometry_comparison.py
覆盖：半交叠、相离、边相切/点相切不算面、全等、包含、整体偏移（等面积仍能检出）、
退化 point/line 不算重叠面、200 组随机多边形两侧面积守恒恒等式。
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from src.services.hull import convex_hull  # noqa: E402
from src.services.polygon_overlap import convex_overlap  # noqa: E402


def area_of(vertices):
    return convex_overlap(vertices, vertices)['overlap_area']


def test_fixed_cases():
    base = [(0., 0.), (1., 0.), (1., 1.), (0., 1.)]
    ret_half = [(0.5, 0.), (1.5, 0.), (1.5, 1.), (0.5, 1.)]
    assert abs(convex_overlap(base, ret_half)['overlap_area'] - 0.5) < 1e-12
    assert len(convex_overlap(base, ret_half)['overlap_vertices']) == 4

    # 相离：零交叠面、空交叠顶点
    disjoint = convex_overlap(base, [(3., 3.), (4., 3.), (4., 4.), (3., 4.)])
    assert disjoint['overlap_area'] == 0.0 and disjoint['overlap_vertices'] == []

    # 边相切：共享一条边，不算重叠面
    edge = convex_overlap(base, [(1., 0.), (2., 0.), (2., 1.), (1., 1.)])
    assert edge['overlap_area'] == 0.0 and edge['overlap_vertices'] == []

    # 点相切：仅共享一个角点，不算重叠面
    corner = convex_overlap(base, [(1., 1.), (2., 1.), (2., 2.), (1., 2.)])
    assert corner['overlap_area'] == 0.0 and corner['overlap_vertices'] == []

    # 全等：交叠=全面积
    assert abs(convex_overlap(base, base)['overlap_area'] - 1.0) < 1e-12

    # 包含：小框完全在大框内，交叠=小框面积
    big = [(0., 0.), (10., 0.), (10., 10.), (0., 10.)]
    small = [(2., 2.), (5., 2.), (5., 5.), (2., 5.)]
    assert abs(convex_overlap(big, small)['overlap_area'] - 9.0) < 1e-12

    # 两直角三角形交叠区域 (1,1)(3,1)(1,3)，面积 2.0
    tri_a = [(0., 0.), (4., 0.), (0., 4.)]
    tri_b = [(1., 1.), (5., 1.), (1., 5.)]
    assert abs(convex_overlap(tri_a, tri_b)['overlap_area'] - 2.0) < 1e-12


def test_overall_shift_detected():
    # 整体平移：两次凸包面积相等，但交叠<面积，新增/减少>0，单看面积相等会漏检
    pts = [(math.cos(t) * 5 + 1000, math.sin(t) * 3 + 2000)
           for t in [i * 2 * math.pi / 12 for i in range(12)]]
    h1 = convex_hull(pts)
    h2 = convex_hull([[p[0] + 2.0, p[1] + 1.5] for p in pts])
    assert abs(h1['area'] - h2['area']) < 1e-9
    overlap = convex_overlap(h1['vertices'], h2['vertices'])['overlap_area']
    added, removed = h2['area'] - overlap, h1['area'] - overlap
    assert 0.0 < overlap < h1['area']
    assert added > 0.0 and removed > 0.0


def test_degenerate_not_face():
    base = [(0., 0.), (1., 0.), (1., 1.), (0., 1.)]
    line = [(0., 0.), (1., 0.)]
    point = [(0., 0.)]
    assert convex_overlap(line, base)['overlap_area'] == 0.0
    assert convex_overlap(line, line)['overlap_area'] == 0.0
    assert convex_overlap(point, base)['overlap_area'] == 0.0
    assert convex_overlap(point, point)['overlap_vertices'] == []


def test_conservation_random():
    rng = random.Random(7)
    for _ in range(200):
        def rand_poly(n):
            pts = sorted((rng.uniform(-50, 50), rng.uniform(-50, 50)) for _ in range(n))
            return convex_hull([[p[0] + 1000, p[1] + 2000] for p in pts])['vertices']

        a = rand_poly(rng.randint(4, 12))
        b = rand_poly(rng.randint(4, 12))
        overlap = convex_overlap(a, b)['overlap_area']
        area_a, area_b = area_of(a), area_of(b)
        added, removed = area_b - overlap, area_a - overlap
        # 净变化 = 新增 - 减少 = 复测面积 - 基准面积
        assert abs((area_b - area_a) - (added - removed)) < 1e-6
        assert abs((area_a - (overlap + removed))) < 1e-6
        assert abs((area_b - (overlap + added))) < 1e-6


if __name__ == '__main__':
    test_fixed_cases()
    test_overall_shift_detected()
    test_degenerate_not_face()
    test_conservation_random()
    print('ALL GEOMETRY TESTS PASSED')
