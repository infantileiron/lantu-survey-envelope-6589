"""复测比较服务决策逻辑的独立测试（纯标准库，不依赖 MySQL/Redis/FastAPI）。

运行：python3 -I test_comparison_logic.py
用真实 services.analysis.analyze 生成两次运行 result，再交给 comparison_logic.compare_results，
覆盖：整体偏移但等面积仍检出、配对/缺组单列、口径不兼容拒绝、退化点线零交叠、两侧面积守恒、冻结校验和。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from src.services.analysis import analyze  # noqa: E402
from src.services.comparison_logic import (  # noqa: E402
    ComparisonError,
    compare_results,
)

POLICY = {
    'id': 'p1', 'name': '口径', 'deduplication': 'exact',
    'area_tie_relative': 1e-12, 'algorithm_version': 'andrews-edge-enumeration-v1',
    'created_at': 't0',
}


def make_snapshot(groups, coordinate_system='local_m', policy=None):
    return {
        'survey': {
            'id': 's', 'name': '测组', 'source': 'demo.json',
            'coordinate_system': coordinate_system, 'groups': groups, 'created_at': 't0',
        },
        'policy': policy or dict(POLICY),
    }


def group(gid, name, pts):
    return {
        'group_id': gid, 'name': name,
        'points': [{'point_id': f'{gid}-P{i:03}', 'x': x, 'y': y}
                   for i, (x, y) in enumerate(pts)],
    }


def square(gid, name, ox, oy, w=10.0):
    pts = [(ox, oy), (ox + w, oy), (ox + w, oy + w), (ox, oy + w)]
    pts += [(ox + w * 0.5, oy + w * 0.3), (ox + w * 0.2, oy + w * 0.7)]
    return group(gid, name, pts)


def run_result(snapshot, ids):
    return analyze(snapshot, ids)


def test_paired_missing_and_shift():
    base_groups = [
        square('G01', '方形A', 0.0, 0.0),
        square('G02', '方形B', 100.0, 100.0, 8.0),
        group('G03', '共线', [(500.0 + i, 600.0 + 2 * i) for i in range(20)]),
        group('G04', '单位置', [(700.0, 700.0)] * 10),
    ]
    # 复测：G01 整体平移（面积不变）、G02 放大、G03 共线保留、G04 缺组、新增 G05
    retest_groups = [
        square('G01', '方形A', 3.0, 2.0),
        square('G02', '方形B', 100.0, 100.0, 9.0),
        group('G03', '共线', [(500.0 + i, 600.0 + 2 * i) for i in range(20)]),
        square('G05', '新增组', -50.0, -50.0, 6.0),
    ]
    base = run_result(make_snapshot(base_groups), ['G01', 'G02', 'G03', 'G04'])
    retest = run_result(make_snapshot(retest_groups), ['G01', 'G02', 'G03', 'G05'])
    out = compare_results(base, retest)
    by = {g['group_id']: g for g in out['groups']}

    # 配对 3 组、缺组 2 组（G04 基准独有、G05 复测独有）
    assert out['totals']['paired_group_count'] == 3
    assert out['totals']['missing_group_count'] == 2
    assert by['G04']['comparison_status'] == 'missing_in_retest'
    assert by['G05']['comparison_status'] == 'missing_in_baseline'
    assert by['G04']['overlap_area'] is None and by['G05']['added_area'] is None

    # G01 整体平移：两次凸包面积相等，但交叠<面积、新增与减少都>0（单看面积相等会漏检）
    g01 = by['G01']
    assert abs(g01['baseline_area'] - g01['retest_area']) < 1e-9
    assert 0.0 < g01['overlap_area'] < g01['baseline_area']
    assert g01['added_area'] > 0.0 and g01['removed_area'] > 0.0
    assert g01['conservation_ok']

    # G02 放大：净变化为正，新增>减少
    g02 = by['G02']
    assert g02['net_area_change'] > 0 and g02['added_area'] > g02['removed_area']
    assert g02['conservation_ok']

    # G03 共线（line/line）：退化几何零交叠面
    g03 = by['G03']
    assert g03['baseline_geometry_type'] == 'line'
    assert g03['overlap_area'] == 0.0 and g03['conservation_ok']

    # 总量守恒
    t = out['totals']
    assert t['conservation_ok_total']
    assert abs(t['retest_area_total'] - t['baseline_area_total']
               - (t['added_area_total'] - t['removed_area_total'])) < 1e-6
    assert len(out['checksum']) == 64
    print('paired/missing/shift/conservation OK')


def test_incompatible_rejected():
    snap_a = make_snapshot([square('G01', 'a', 0.0, 0.0)])
    # 不同去重口径
    snap_b = make_snapshot(
        [square('G01', 'a', 1.0, 1.0)],
        policy={**POLICY, 'deduplication': 'reject'},
    )
    try:
        compare_results(run_result(snap_a, ['G01']), run_result(snap_b, ['G01']))
        raise AssertionError('应当拒绝口径不兼容的比较')
    except ComparisonError as exc:
        assert '去重口径不一致' in str(exc)

    # 不同坐标系
    snap_c = make_snapshot([square('G01', 'a', 0.0, 0.0)], coordinate_system='wgs84_lonlat')
    try:
        compare_results(run_result(snap_a, ['G01']), run_result(snap_c, ['G01']))
        raise AssertionError('应当拒绝坐标系不兼容的比较')
    except ComparisonError as exc:
        assert '坐标系不一致' in str(exc)

    # 不同算法版本
    snap_d = make_snapshot(
        [square('G01', 'a', 0.0, 0.0)],
        policy={**POLICY, 'algorithm_version': 'other-v2'},
    )
    try:
        compare_results(run_result(snap_a, ['G01']), run_result(snap_d, ['G01']))
        raise AssertionError('应当拒绝算法版本不兼容的比较')
    except ComparisonError as exc:
        assert '算法版本不一致' in str(exc)
    print('incompatible rejection OK')


def test_tangent_and_point_groups_zero_overlap():
    # 两方形仅边相接（一个 x 从 0..10，另一个 10..20），交叠面必须为 0
    a = run_result(make_snapshot([square('G01', 'a', 0.0, 0.0)]), ['G01'])
    b = run_result(make_snapshot([square('G01', 'a', 10.0, 0.0)]), ['G01'])
    out = compare_results(a, b)
    g = out['groups'][0]
    assert g['overlap_area'] == 0.0 and g['overlap_vertices'] == []
    # 相切时：新增=复测全面积、减少=基准全面积，仍然守恒
    assert abs(g['added_area'] - g['retest_area']) < 1e-9
    assert abs(g['removed_area'] - g['baseline_area']) < 1e-9
    assert g['conservation_ok']
    print('tangent zero-overlap OK')


def test_frozen_checksum_stable_and_distinct():
    snap = make_snapshot([square('G01', 'a', 0.0, 0.0)])
    base = run_result(snap, ['G01'])
    r1 = run_result(make_snapshot([square('G01', 'a', 1.0, 0.0)]), ['G01'])
    r2 = run_result(make_snapshot([square('G01', 'a', 2.0, 0.0)]), ['G01'])
    c1 = compare_results(base, r1)
    c1_again = compare_results(base, r1)
    c2 = compare_results(base, r2)
    assert c1['checksum'] == c1_again['checksum']   # 同输入可重复
    assert c1['checksum'] != c2['checksum']          # 不同运行结果不同校验和
    print('frozen checksum OK')


if __name__ == '__main__':
    test_paired_missing_and_shift()
    test_incompatible_rejected()
    test_tangent_and_point_groups_zero_overlap()
    test_frozen_checksum_stable_and_distinct()
    print('ALL COMPARISON LOGIC TESTS PASSED')
