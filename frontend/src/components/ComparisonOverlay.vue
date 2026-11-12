<script setup lang="ts">
import {computed,ref} from 'vue';
import type {ComparisonGroup} from '../types/domain';
import {num} from '../utils/format';
const props=defineProps<{group:ComparisonGroup}>();
const showBase=ref(true),showRetest=ref(true),showOverlap=ref(true),showAdded=ref(true),showRemoved=ref(true);
type Pt=[number,number];
const rings=computed(()=>({
  base:props.group.baseline_hull_vertices as Pt[],
  retest:props.group.retest_hull_vertices as Pt[],
  overlap:props.group.overlap_vertices as Pt[],
}));
// 新增=复测减交叠、减少=基准减交叠，仅作等比例示意（以明细表面积数值为准）
const addedRings=computed<Pt[][]>(()=>differenceRings(rings.value.retest,rings.value.overlap));
const removedRings=computed<Pt[][]>(()=>differenceRings(rings.value.base,rings.value.overlap));
function differenceRings(outer:Pt[],hole:Pt[]):Pt[][]{
  if(outer.length<3)return [];
  return hole.length>=3?[outer,hole]:[outer];
}
const bounds=computed(()=>{
  const all:Pt[]=[];
  for(const r of [rings.value.base,rings.value.retest,rings.value.overlap])all.push(...r);
  if(!all.length)return null;
  let x0=Math.min(...all.map(p=>p[0])),x1=Math.max(...all.map(p=>p[0]));
  let y0=Math.min(...all.map(p=>p[1])),y1=Math.max(...all.map(p=>p[1]));
  const pad=Math.max(x1-x0,y1-y0,1)*.08;x0-=pad;x1+=pad;y0-=pad;y1+=pad;
  const scale=Math.min(860/(x1-x0),400/(y1-y0)),left=70+(860-(x1-x0)*scale)/2,top=34+(400-(y1-y0)*scale)/2;
  return{x0,x1,y0,y1,scale,left,top};
});
const sx=(x:number)=>bounds.value?bounds.value.left+(x-bounds.value.x0)*bounds.value.scale:0;
const sy=(y:number)=>bounds.value?bounds.value.top+(bounds.value.y1-y)*bounds.value.scale:0;
const pts=(ring:Pt[])=>ring.map(p=>sx(p[0])+','+sy(p[1])).join(' ');
const ringPath=(ring:Pt[])=>ring.length>=3?('M'+ring.map(p=>sx(p[0])+' '+sy(p[1])).join('L')+'Z'):'';
const diffPath=(rs:Pt[][])=>rs.map(ringPath).join(' ');
</script>
<template>
<div class="survey-plot comparison-plot">
  <div class="plot-title"><strong>{{group.group_id}} 两侧凸包叠看 · 等比例米制平面</strong><span>local_m · x/y同比例 · 点线/相切不计重叠面</span></div>
  <p v-if="group.comparison_status!=='paired'" class="notice">{{group.overlap_note}}</p>
  <div class="boundary-legend">
    <label><input type="checkbox" v-model="showBase" aria-label="显示基准凸包"/><i class="base-key"/>基准凸包</label>
    <label><input type="checkbox" v-model="showRetest" aria-label="显示复测凸包"/><i class="retest-key"/>复测凸包</label>
    <label><input type="checkbox" v-model="showOverlap" aria-label="显示交叠面"/><i class="overlap-key"/>交叠面</label>
    <label><input type="checkbox" v-model="showAdded" aria-label="显示新增面"/><i class="added-key"/>复测新增</label>
    <label><input type="checkbox" v-model="showRemoved" aria-label="显示减少面"/><i class="removed-key"/>基准减少</label>
  </div>
  <div v-if="!bounds" class="empty"><span>NO 2D FACE</span><p>该点组为缺组或退化点/线，没有可叠看的二维面（点线、相切不计重叠面）。</p></div>
  <svg v-else viewBox="0 0 1000 500" role="img" :aria-label="group.group_id+'两侧凸包与交叠差异'">
    <g v-for="f in [0,.25,.5,.75,1]" :key="f">
      <line :x1="sx(bounds.x0)" :x2="sx(bounds.x1)" :y1="sy(bounds.y0+f*(bounds.y1-bounds.y0))" :y2="sy(bounds.y0+f*(bounds.y1-bounds.y0))" stroke="#e2dccb"/>
      <line :x1="sx(bounds.x0+f*(bounds.x1-bounds.x0))" :x2="sx(bounds.x0+f*(bounds.x1-bounds.x0))" :y1="sy(bounds.y0)" :y2="sy(bounds.y1)" stroke="#ece6d6"/>
      <text :x="sx(bounds.x0)-9" :y="sy(bounds.y0+f*(bounds.y1-bounds.y0))+4" text-anchor="end">{{num(bounds.y0+f*(bounds.y1-bounds.y0),2)}}</text>
      <text :x="sx(bounds.x0+f*(bounds.x1-bounds.x0))" :y="sy(bounds.y0)+22" text-anchor="middle">{{num(bounds.x0+f*(bounds.x1-bounds.x0),2)}}</text>
    </g>
    <path v-if="showRemoved&&removedRings.length" :d="diffPath(removedRings)" fill-rule="evenodd" class="fill-removed"/>
    <path v-if="showAdded&&addedRings.length" :d="diffPath(addedRings)" fill-rule="evenodd" class="fill-added"/>
    <polygon v-if="showOverlap&&rings.overlap.length>=3" :points="pts(rings.overlap)" class="fill-overlap"/>
    <polygon v-if="showBase&&rings.base.length>=3" :points="pts(rings.base)" class="stroke-base"/>
    <polygon v-if="showRetest&&rings.retest.length>=3" :points="pts(rings.retest)" class="stroke-retest"/>
    <text :x="sx(bounds.x0)" y="18">y / 米</text>
    <text :x="sx(bounds.x1)" :y="sy(bounds.y0)+46" text-anchor="end">x / 米</text>
  </svg>
  <p class="muted">新增/减少用 even-odd 挖空示意，精确面积以差异明细表为准；退化 point/line 只画点/线，不生成填充面。{{group.overlap_note}}</p>
</div>
</template>
