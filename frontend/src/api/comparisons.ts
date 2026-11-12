import {request} from './client';import type {Comparison} from '../types/domain';
export const list=()=>request<Comparison[]>('/comparisons');
export const create=(data:unknown)=>request<Comparison>('/comparisons',data);
