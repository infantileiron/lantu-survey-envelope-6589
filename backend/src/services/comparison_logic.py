"""复测比较的纯决策逻辑：只依赖标准库与本项目几何模块，不接触 DB/HTTP。

服务层 comparisons.py 负责加载运行、翻译异常与持久化；本模块负责：
- 口径兼容性判定（不兼容抛 ComparisonError，拒绝比较）；
- 按点组编号配对、缺组单列；
- 凸包交叠/新增/减少面积与两侧面积守恒核对；
- 汇总与冻结校验和。
"""
import hashlib
import json

from src.services.polygon_overlap import convex_overlap

# 面积守恒核对容差：相对参考面积尺度的比例，外加绝对米²下限，吸收浮点求和噪声。
CONSERVATION_REL_TOL = 1e-9
CONSERVATION_ABS_TOL = 1e-6


class ComparisonError(ValueError):
    """口径不兼容等可向用户返回的比较拒绝原因。"""


def compatibility_problems(result_a, result_b):
    """返回不兼容原因列表；空列表表示口径兼容，可以比较。"""
    problems = []
    if result_a.get('coordinate_system') != result_b.get('coordinate_system'):
        problems.append(
            f"坐标系不一致：{result_a.get('coordinate_system')} vs "
            f"{result_b.get('coordinate_system')}"
        )
    pa, pb = result_a.get('policy', {}), result_b.get('policy', {})
    if pa.get('deduplication') != pb.get('deduplication'):
        problems.append(
            f"去重口径不一致：{pa.get('deduplication')} vs {pb.get('deduplication')}"
        )
    if pa.get('area_tie_relative') != pb.get('area_tie_relative'):
        problems.append(
            "同面积方向容差不一致："
            f"{pa.get('area_tie_relative')} vs {pb.get('area_tie_relative')}"
        )
    if pa.get('algorithm_version') != pb.get('algorithm_version'):
        problems.append(
            f"算法版本不一致：{pa.get('algorithm_version')} vs "
            f"{pb.get('algorithm_version')}"
        )
    return problems


def _group_index(result):
    return {g['group_id']: g for g in result['groups']}


def _compare_group(group_id, base_group, retest_group):
    base_hull, retest_hull = base_group['hull'], retest_group['hull']
    base_area = float(base_hull['area'])
    retest_area = float(retest_hull['area'])
    base_kind, retest_kind = base_hull['geometry_type'], retest_hull['geometry_type']
    base_vertices = base_hull.get('vertices', [])
    retest_vertices = retest_hull.get('vertices', [])

    overlap_vertices, overlap_area, overlap_note = [], 0.0, ''
    if base_kind == 'polygon' and retest_kind == 'polygon':
        ov = convex_overlap(base_vertices, retest_vertices, CONSERVATION_REL_TOL)
        overlap_area = ov['overlap_area']
        overlap_vertices = ov['overlap_vertices']
        if overlap_area == 0.0:
            overlap_note = '两凸包相离或仅相切：点/线接触不计重叠面，交叠面积为0'
    else:
        kinds = {'point': '单位置点', 'line': '共线', 'polygon': '面'}
        overlap_note = (
            f"基准为{kinds[base_kind]}、复测为{kinds[retest_kind]}，"
            '退化几何没有二维面，点线与相切不计重叠面，交叠面积为0'
        )

    added_area = retest_area - overlap_area
    removed_area = base_area - overlap_area
    conservation_gap = (retest_area - base_area) - (added_area - removed_area)
    return {
        'group_id': group_id,
        'name_baseline': base_group.get('name', ''),
        'name_retest': retest_group.get('name', ''),
        'comparison_status': 'paired',
        'baseline_geometry_type': base_kind,
        'retest_geometry_type': retest_kind,
        'baseline_area': base_area,
        'retest_area': retest_area,
        'overlap_area': overlap_area,
        'added_area': added_area,
        'removed_area': removed_area,
        'net_area_change': retest_area - base_area,
        'conservation_gap': conservation_gap,
        'conservation_ok': abs(conservation_gap) <= max(
            CONSERVATION_ABS_TOL,
            CONSERVATION_REL_TOL * max(1.0, base_area, retest_area),
        ),
        'overlap_note': overlap_note,
        'baseline_hull_vertices': base_vertices,
        'retest_hull_vertices': retest_vertices,
        'overlap_vertices': overlap_vertices,
    }


def _missing_group(group_id, group, side):
    hull = group['hull']
    return {
        'group_id': group_id,
        'name_baseline': group.get('name', '') if side == 'baseline' else '',
        'name_retest': group.get('name', '') if side == 'retest' else '',
        'comparison_status': 'missing_in_retest' if side == 'baseline' else 'missing_in_baseline',
        'baseline_geometry_type': hull['geometry_type'] if side == 'baseline' else None,
        'retest_geometry_type': hull['geometry_type'] if side == 'retest' else None,
        'baseline_area': float(hull['area']) if side == 'baseline' else None,
        'retest_area': float(hull['area']) if side == 'retest' else None,
        'overlap_area': None,
        'added_area': None,
        'removed_area': None,
        'net_area_change': None,
        'conservation_gap': None,
        'conservation_ok': None,
        'overlap_note': (
            '该点组仅存在于基准运行，复测缺组，单列不参与交叠比较'
            if side == 'baseline'
            else '该点组仅存在于复测运行，基准缺组，单列不参与交叠比较'
        ),
        'baseline_hull_vertices': hull.get('vertices', []) if side == 'baseline' else [],
        'retest_hull_vertices': hull.get('vertices', []) if side == 'retest' else [],
        'overlap_vertices': [],
    }


def compare_results(baseline_result, retest_result):
    """对两份已成功运行的 result 做完整比较，返回可冻结的结果字典。"""
    problems = compatibility_problems(baseline_result, retest_result)
    if problems:
        raise ComparisonError('口径不兼容，拒绝比较：' + '；'.join(problems))

    base_idx = _group_index(baseline_result)
    retest_idx = _group_index(retest_result)
    paired, missing = [], []
    for gid in sorted(set(base_idx) | set(retest_idx)):
        in_base, in_retest = gid in base_idx, gid in retest_idx
        if in_base and in_retest:
            paired.append(_compare_group(gid, base_idx[gid], retest_idx[gid]))
        elif in_base:
            missing.append(_missing_group(gid, base_idx[gid], 'baseline'))
        else:
            missing.append(_missing_group(gid, retest_idx[gid], 'retest'))

    def total(rows, key):
        return sum(r[key] for r in rows if r[key] is not None)

    totals = {
        'paired_group_count': len(paired),
        'missing_group_count': len(missing),
        'baseline_area_total': total(paired, 'baseline_area'),
        'retest_area_total': total(paired, 'retest_area'),
        'overlap_area_total': total(paired, 'overlap_area'),
        'added_area_total': total(paired, 'added_area'),
        'removed_area_total': total(paired, 'removed_area'),
        'net_area_change_total': total(paired, 'net_area_change'),
    }
    totals['conservation_gap_total'] = (
        totals['retest_area_total'] - totals['baseline_area_total']
        - (totals['added_area_total'] - totals['removed_area_total'])
    )
    totals['conservation_ok_total'] = (
        all(r['conservation_ok'] for r in paired)
        and abs(totals['conservation_gap_total']) <= max(
            CONSERVATION_ABS_TOL,
            CONSERVATION_REL_TOL * max(
                1.0, totals['baseline_area_total'], totals['retest_area_total']
            ),
        )
    )

    policy = baseline_result['policy']
    payload = {
        'coordinate_system': baseline_result['coordinate_system'],
        'policy_fingerprint': {
            'deduplication': policy['deduplication'],
            'area_tie_relative': policy['area_tie_relative'],
            'algorithm_version': policy['algorithm_version'],
        },
        'groups': paired + missing,
        'totals': totals,
        'conservation_rule': (
            '每个配对点组满足 复测面积=交叠+新增、基准面积=交叠+减少；'
            '净变化=新增-减少=(复测-基准)。容差 '
            f'rel={CONSERVATION_REL_TOL}, abs={CONSERVATION_ABS_TOL}m²。'
            '点/线/相切不计重叠面；缺组单列不参与面积守恒。'
        ),
        'frozen_notice': (
            '比较在创建时冻结双方运行来源与全部几何，源数据更新或出现后续运行'
            '均不重算、不自动换用。'
        ),
    }
    digest_base = {
        'baseline_checksum': baseline_result.get('checksum'),
        'retest_checksum': retest_result.get('checksum'),
        'groups': payload['groups'],
        'totals': payload['totals'],
    }
    payload['checksum'] = hashlib.sha256(
        json.dumps(digest_base, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return payload
