import { Routes } from '@angular/router';

import { exigirEnvio } from './core/auth.guard';

export const routes: Routes = [
  {
    path: '',
    title: 'Unidades · FatecOrg',
    loadComponent: () => import('./features/unidades/unidades').then((m) => m.Unidades),
  },
  {
    path: 'busca',
    title: 'Buscar · FatecOrg',
    loadComponent: () => import('./features/busca/busca').then((m) => m.Busca),
  },
  {
    path: 'unidades/:unidade/cursos/:curso/comparar',
    title: 'Comparar versões · FatecOrg',
    loadComponent: () => import('./features/comparar/comparar').then((m) => m.Comparar),
  },
  {
    path: 'unidades/:unidade/cursos/:curso',
    title: 'Histórico do curso · FatecOrg',
    loadComponent: () => import('./features/curso/curso').then((m) => m.Curso),
  },
  {
    path: 'documentos',
    title: 'Documentos · FatecOrg',
    loadComponent: () => import('./features/documentos/documentos').then((m) => m.Documentos),
  },
  {
    path: 'entrar',
    title: 'Entrar · FatecOrg',
    loadComponent: () => import('./features/entrar/entrar').then((m) => m.Entrar),
  },
  {
    path: 'enviar',
    title: 'Enviar documento · FatecOrg',
    canActivate: [exigirEnvio],
    loadComponent: () => import('./features/enviar/enviar').then((m) => m.Enviar),
  },
  { path: '**', redirectTo: '' },
];
