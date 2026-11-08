import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { Auth } from './core/auth';

@Component({
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  selector: 'app-root',
  templateUrl: './app.html',
})
export class App {
  protected readonly auth = inject(Auth);
  private readonly router = inject(Router);

  constructor() {
    void this.auth.restaurar();
  }

  protected sair(): void {
    this.auth.sair().subscribe(() => void this.router.navigateByUrl('/'));
  }
}
