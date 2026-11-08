import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Auth } from './auth';

/** Só coordenador e admin do polo enviam documentos. A API confere de novo; isto é só a tela. */
export const exigirEnvio: CanActivateFn = async (_rota, estado) => {
  const auth = inject(Auth);
  const router = inject(Router);
  await auth.restaurar();
  return auth.podeEnviar()
    ? true
    : router.createUrlTree(['/entrar'], { queryParams: { voltar: estado.url } });
};
