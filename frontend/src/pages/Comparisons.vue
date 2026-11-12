<script setup lang="ts">
import {ref,computed} from 'vue';
import type {Workspace} from '../stores/workspace';
import {create} from '../api/comparisons';
import {useAction} from '../hooks/useAction';
import Heading from '../components/common/Heading.vue';
import Notice from '../components/common/Notice.vue';
import Empty from '../components/common/Empty.vue';
import ComparisonOverlay from '../components/ComparisonOverlay.vue';
import ComparisonTable from '../components/ComparisonTable.vue';
import {num,short} from '../utils/format';

const props=defineProps<{data:Workspace;canWrite:boolean;refresh:()=>Promise<void>}>();
const name=ref('基准—复测凸包差异比较');
const baselineRunId=ref('');
const retestRunId=ref('');
const comparisonId=ref('');
const gid=ref('');
const {busy,error,notice,act}=useAction();

const completedRuns=computed(()=>props.data.runs.filter(r=>r.status==='completed'));
const studyName=(runId:string)=>{const r=props.data.runs.find(x=>x.id===runId);return r?props.data.studies.find(s=>s.id===r.study_id)?.name||short(runId):'';};
const runLabel=(r:{id:string;study_id:string;created_at:string})=>`${studyName(r.id)} · ${r.created_at.slice(0,19).replace('T',' ')} · ${short(r.id)}`;
const selected=computed(()=>props.data.comparisons.find(c=>c.id===comparisonId.value)||props.data.comparisons[0]);
const activeGroup=computed(()=>{
 if(!selected.value)return undefined;
 return selected.value.result.groups.find(g=>g.group_id===gid.value)||selected.value.result.groups[0];
});
function pickGroup(id:string){gid.value=id;}
function stamp(v:string){return v?v.slice(0,19).replace('T',' '):'';}
</script>

<template>
<div class="comparisons-page">
<Heading index="07 / RETEST COMPARISON" title="等面积也会偏移，逐组看交叠、新增与减少。" detail="选定基准研究与复测研究的两次成功运行，按点组编号比较凸包交叠/新增/减少并核对两侧面积守恒；口径不兼容直接拒绝，缺组单列，点线与相切不算重叠面。"/>

<section v-if="canWrite" class="form-section">
<form class="form-grid" @submit.prevent="act(async()=>{const c=await create({name,baseline_run_id:baselineRunId,retest_run_id:retestRunId});await refresh();comparisonId=c.id;},'比较已创建并冻结双方来源，历史结果不随后续运行重算')">
<label>比较名称<input aria-label="比较名称" required minlength="2" maxlength="160" v-model="name"></label>
<label>基准研究的成功运行（旧）
<select aria-label="基准运行" required v-model="baselineRunId">
<option value="" disabled>选择基准运行</option>
<option v-for="r in completedRuns" :key="'b'+r.id" :value="r.id">{{runLabel(r)}}</option>
</select>
</label>
<label>复测研究的成功运行（新）
<select aria-label="复测运行" required v-model="retestRunId">
<option value="" disabled>选择复测运行</option>
<option v-for="r in completedRuns" :key="'r'+r.id" :value="r.id">{{runLabel(r)}}</option>
</select>
</label>
<p class="muted">仅可选已成功完成的运行；同一运行不能与自身比较。坐标系/去重口径/同面积容差/算法版本不一致时后端拒绝比较。</p>
<button class="primary" :disabled="busy||!baselineRunId||!retestRunId||baselineRunId===retestRunId">冻结并计算凸包差异</button>
</form>
<Notice :error="error" :notice="notice"/>
</section>

<Empty v-if="!data.comparisons.length">先让基准研究与复测研究各完成一次成功运行，再在此选择两次运行做凸包差异比较。</Empty>

<template v-else>
<label class="selector">已冻结的历史比较
<select aria-label="选择历史比较" v-model="comparisonId">
<option v-for="c in data.comparisons" :key="c.id" :value="c.id">{{c.name}} · {{stamp(c.created_at)}}</option>
</select>
</label>

<article v-if="selected" class="comparison-detail">
  <div class="result-meta"><span>CMP {{short(selected.id)}}</span><span>SHA256 {{short(selected.checksum)}}</span><span>创建人 {{selected.created_by}}</span><span>{{stamp(selected.created_at)}}</span></div>

  <div class="source-grid">
    <section class="source-card base">
      <p class="eyebrow">基准来源 / BASELINE</p>
      <h3>{{selected.baseline_source.study_name}}</h3>
      <p>运行 {{short(selected.baseline_source.run_id)}} · {{stamp(selected.baseline_source.run_created_at)}}</p>
      <p>测组 {{selected.baseline_source.survey_name}}<br>来源文件 {{selected.baseline_source.survey_source}}</p>
      <p>口径 {{selected.baseline_source.policy_name}} · {{selected.baseline_source.deduplication}} · 容差{{selected.baseline_source.area_tie_relative}} · {{selected.baseline_source.algorithm_version}}</p>
      <p class="mono">结果校验和 {{short(selected.baseline_source.result_checksum)}}</p>
    </section>
    <section class="source-card retest">
      <p class="eyebrow">复测来源 / RETEST</p>
      <h3>{{selected.retest_source.study_name}}</h3>
      <p>运行 {{short(selected.retest_source.run_id)}} · {{stamp(selected.retest_source.run_created_at)}}</p>
      <p>测组 {{selected.retest_source.survey_name}}<br>来源文件 {{selected.retest_source.survey_source}}</p>
      <p>口径 {{selected.retest_source.policy_name}} · {{selected.retest_source.deduplication}} · 容差{{selected.retest_source.area_tie_relative}} · {{selected.retest_source.algorithm_version}}</p>
      <p class="mono">结果校验和 {{short(selected.retest_source.result_checksum)}}</p>
    </section>
  </div>
  <p class="notice">{{selected.result.frozen_notice}}</p>

  <div class="risk-summary">
    <div><small>配对点组 / 缺组</small><b>{{selected.result.totals.paired_group_count}}<i>/ {{selected.result.totals.missing_group_count}}</i></b><span>缺组单列，不参与面积守恒</span></div>
    <div><small>交叠 / 新增 / 减少（m²，配对组合计）</small><b>{{num(selected.result.totals.overlap_area_total)}}<i>/ {{num(selected.result.totals.added_area_total)}} / {{num(selected.result.totals.removed_area_total)}}</i></b><span>复测面积={{num(selected.result.totals.retest_area_total)}} 基准面积={{num(selected.result.totals.baseline_area_total)}}</span></div>
    <div><small>两侧面积守恒核对</small><b :class="selected.result.totals.conservation_ok_total?'ok':'bad'">{{selected.result.totals.conservation_ok_total?'守恒 ✓':'偏差'}}</b><span>净变化 {{num(selected.result.totals.net_area_change_total)}} m² · 守恒差 {{num(selected.result.totals.conservation_gap_total,6)}}</span></div>
  </div>

  <ComparisonTable :groups="selected.result.groups" :active-group="activeGroup?.group_id||''" @select="pickGroup"/>

  <ComparisonOverlay v-if="activeGroup" :key="activeGroup.group_id" :group="activeGroup"/>

  <div class="section-rule"><h2>差异明细与守恒规则</h2><span>点击表格行切换点组叠看</span></div>
  <div v-if="activeGroup" class="group-detail">
    <h3>{{activeGroup.group_id}} · {{activeGroup.name_baseline||activeGroup.name_retest}}</h3>
    <p class="muted">{{activeGroup.overlap_note}}</p>
    <div class="quantiles">
      <span>基准面积 <b>{{num(activeGroup.baseline_area)}}</b></span>
      <span>复测面积 <b>{{num(activeGroup.retest_area)}}</b></span>
      <span>交叠 <b>{{num(activeGroup.overlap_area)}}</b></span>
      <span>新增 <b>{{num(activeGroup.added_area)}}</b></span>
      <span>减少 <b>{{num(activeGroup.removed_area)}}</b></span>
      <span>净变化 <b>{{num(activeGroup.net_area_change)}}</b></span>
    </div>
  </div>

  <details>
    <summary>口径指纹、面积守恒规则与冻结说明</summary>
    <p>坐标系 {{selected.result.coordinate_system}}；去重 {{selected.result.policy_fingerprint.deduplication}}；同面积容差 {{selected.result.policy_fingerprint.area_tie_relative}}；算法版本 {{selected.result.policy_fingerprint.algorithm_version}}。</p>
    <p>{{selected.result.conservation_rule}}</p>
    <p>{{selected.result.frozen_notice}}</p>
    <p class="mono">{{selected.result.checksum}}</p>
  </details>
</article>
</template>
</div>
</template>
