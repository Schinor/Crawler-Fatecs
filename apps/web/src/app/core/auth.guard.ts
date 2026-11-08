import { Signal, inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Auth } from './auth';

/** Espera a sessão ser restaurada e confere a permissão. A API confere de novo; isto é só a tela. */
function exigir(permissao: (auth: Auth) => Signal<boolean>): CanActivateFn {
  return async (_rota, estado) => {
    const auth = inject(Auth);
    const router = inject(Router);
    await auth.restaurar();
    return permissao(auth)()
      ? true
      : router.createUrlTree(['/entrar'], { queryParams: { voltar: estado.url } });
  };
}

export const exigirEnvio = exigir((auth) => auth.podeEnviar);
export const exigirAdmin = exigir((auth) => auth.ehAdmin);
