 <script lang="ts">
  import { BRAND } from "../global.js";
  import {
    login,
    logout,
    getMe,
    getStoredUser,
    isAuthenticated,
    type UserInfo,
  } from "./authClient.ts";

  let email = $state("");
  let password = $state("");
  let loading = $state(false);
  let error = $state<string | null>(null);
  let user = $state<UserInfo | null>(getStoredUser());

  async function handleSubmit(e: Event) {
    e.preventDefault();
    loading = true;
    error = null;

    try {
      const result = await login(email, password);
      user = result.user;
      email = "";
      password = "";
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : "Error desconocido";
    } finally {
      loading = false;
    }
  }

  async function handleLogout() {
    await logout();
    user = null;
    error = null;
  }

  async function handleRefresh() {
    const u = await getMe();
    if (u) {
      user = u;
    } else {
      user = null;
    }
  }
</script>

{#if user}
  <div class="card bg-base-100 w-full max-w-sm shadow-xl">
    <div class="card-body">
      <h2 class="card-title">{BRAND.publicName}</h2>
      <p class="text-sm text-base-content/70">Sesión iniciada</p>

      <div class="mt-4 space-y-2">
        <div class="flex justify-between text-sm">
          <span class="font-medium">Email</span>
          <span>{user.email}</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="font-medium">Role</span>
          <span class="badge badge-primary badge-sm">{user.role}</span>
        </div>
        {#if user.username}
          <div class="flex justify-between text-sm">
            <span class="font-medium">Usuario</span>
            <span>{user.username}</span>
          </div>
        {/if}
      </div>

      <div class="card-actions mt-6 justify-between">
        <button class="btn btn-ghost btn-sm" onclick={handleRefresh}>
          Verificar sesión
        </button>
        <button class="btn btn-outline btn-sm" onclick={handleLogout}>
          Cerrar sesión
        </button>
      </div>
    </div>
  </div>
{:else}
  <form
    class="card bg-base-100 w-full max-w-sm shadow-xl"
    onsubmit={handleSubmit}
  >
    <div class="card-body">
      <h2 class="card-title">{BRAND.publicName}</h2>
      <p class="text-sm text-base-content/70">Inicia sesión para continuar</p>

      {#if error}
        <div class="alert alert-error text-sm" role="alert">
          <span>{error}</span>
        </div>
      {/if}

      <div class="form-control">
        <label class="label" for="login-email">
          <span class="label-text">Email</span>
        </label>
        <input
          id="login-email"
          type="email"
          class="input input-bordered w-full"
          required
          bind:value={email}
          disabled={loading}
          autocomplete="email"
        />
      </div>

      <div class="form-control">
        <label class="label" for="login-password">
          <span class="label-text">Contraseña</span>
        </label>
        <input
          id="login-password"
          type="password"
          class="input input-bordered w-full"
          required
          bind:value={password}
          disabled={loading}
          autocomplete="current-password"
        />
      </div>

      <div class="card-actions mt-4">
        <button
          class="btn btn-primary w-full"
          type="submit"
          disabled={loading}
        >
          {#if loading}
            <span class="loading loading-spinner loading-sm"></span>
            Ingresando…
          {:else}
            Ingresar
          {/if}
        </button>
      </div>
    </div>
  </form>
{/if}
