"""复测比较服务层：加载成功运行、口径拒绝翻译、冻结双方来源并持久化。

纯决策在 comparison_logic.compare_results；本模块只处理 DB/HTTP 与来源快照。
比较结果在创建时整体冻结，源数据更新或出现后续运行都不会重算或自动换用运行。
"""
import uuid

from fastapi import HTTPException
from sqlalchemy import select

from src.models import EnvelopeRun, EnvelopeStudy, RunComparison
from src.services.comparison_logic import ComparisonError, compare_results
from src.utils.serialization import serialize
from src.utils.time import now


def _completed_run(db, run_id, label):
    run = db.get(EnvelopeRun, run_id)
    if not run:
        raise HTTPException(404, f'{label}运行不存在')
    if run.status != 'completed':
        raise HTTPException(409, f'{label}运行尚未成功完成，不能参与比较')
    if not run.result or not run.result.get('groups'):
        raise HTTPException(409, f'{label}运行缺少可比较的凸包结果')
    return run


def _run_source(db, run):
    """冻结一次运行的来源指纹：运行本身、所属研究、源测组与口径摘要。"""
    study = db.get(EnvelopeStudy, run.study_id)
    snapshot = study.snapshot if study else {}
    survey = snapshot.get('survey', {})
    policy = snapshot.get('policy', {})
    return {
        'run_id': run.id,
        'run_status': run.status,
        'run_created_at': run.created_at,
        'study_id': run.study_id,
        'study_name': study.name if study else '',
        'survey_id': study.survey_id if study else '',
        'survey_name': survey.get('name', ''),
        'survey_source': survey.get('source', ''),
        'coordinate_system': survey.get('coordinate_system', ''),
        'policy_id': study.policy_id if study else '',
        'policy_name': policy.get('name', ''),
        'deduplication': policy.get('deduplication', ''),
        'area_tie_relative': policy.get('area_tie_relative'),
        'algorithm_version': policy.get('algorithm_version', ''),
        'result_checksum': run.result.get('checksum', ''),
        'selected_group_ids': list(run.result.get('selected_group_ids', [])),
    }


def build_comparison(db, baseline_run_id, retest_run_id):
    """校验并计算，返回 (基准运行, 复测运行, 冻结结果)；口径不兼容则 422 拒绝。"""
    if baseline_run_id == retest_run_id:
        raise HTTPException(422, '基准运行与复测运行须是两次不同的成功运行')
    base_run = _completed_run(db, baseline_run_id, '基准')
    retest_run = _completed_run(db, retest_run_id, '复测')
    try:
        result = compare_results(base_run.result, retest_run.result)
    except ComparisonError as exc:
        raise HTTPException(422, str(exc))
    return base_run, retest_run, result


def create(db, payload, user):
    base_run, retest_run, result = build_comparison(
        db, payload.baseline_run_id, payload.retest_run_id
    )
    if db.scalar(select(RunComparison).where(RunComparison.name == payload.name)):
        raise HTTPException(409, '复测比较名称已存在')
    item = RunComparison(
        id=str(uuid.uuid4()),
        name=payload.name,
        baseline_run_id=payload.baseline_run_id,
        retest_run_id=payload.retest_run_id,
        baseline_source=_run_source(db, base_run),
        retest_source=_run_source(db, retest_run),
        result=result,
        checksum=result['checksum'],
        created_by=user['email'],
        created_at=now(),
    )
    db.add(item)
    db.commit()
    return serialize(item)
