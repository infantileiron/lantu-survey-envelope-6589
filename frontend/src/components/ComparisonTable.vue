<script setup lang="ts">
import type {ComparisonGroup} from '../types/domain';
import {num} from '../utils/format';
defineProps<{groups:ComparisonGroup[];activeGroup:string}>();
const emit=defineEmits<{select:[string]}>();
const statusText=(s:string)=>s==='paired'?'已配对':s==='missing_in_retest'?'复测缺组':'基准缺组';
</script>
<template>
<div class="table-scroll">
<table>
<thead><tr>
<th>点组</th><th>状态</th><th>基准类型</th><th>复测类型</th>
<th>基准面积m²</th><th>复测面积m²</th><th>交叠m²</th><th>新增m²</th><th>减少m²</th><th>净变化m²</th><th>面积守恒</th>
</tr></thead>
<tbody>
<tr v-for="g in groups" :key="g.group_id" :class="{critical:g.comparison_status!=='paired',active:g.group_id===activeGroup}" @click="emit('select',g.group_id)">
<td><b>{{g.group_id}}</b>{{g.name_baseline||g.name_retest}}</td>
<td>{{statusText(g.comparison_status)}}</td>
<td>{{g.baseline_geometry_type||'—'}}</td>
<td>{{g.retest_geometry_type||'—'}}</td>
<td>{{num(g.baseline_area)}}</td>
<td>{{num(g.retest_area)}}</td>
<td>{{num(g.overlap_area)}}</td>
<td>{{num(g.added_area)}}</td>
<td>{{num(g.removed_area)}}</td>
<td :class="(g.net_area_change??0)>0?'pos':(g.net_area_change??0)<0?'neg':''">{{num(g.net_area_change)}}</td>
<td><span v-if="g.conservation_ok===null" class="muted">缺组不核对</span><span v-else :class="g.conservation_ok?'ok':'bad'">{{g.conservation_ok?'守恒✓':'偏差'}}</span></td>
</tr>
</tbody>
</table>
</div>
</template>
