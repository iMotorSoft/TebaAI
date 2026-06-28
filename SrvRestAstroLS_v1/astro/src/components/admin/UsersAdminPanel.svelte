 <script lang="ts">
  import { BRAND, ROUTES } from "../global.js";
  import { getStoredUser, getStoredAccessToken, logout, getMe } from "../auth/authClient.ts";
  import {
    listUsers,
    createUser,
    updateUser,
    activateUser,
    deactivateUser,
    type UserInfo,
    type UserListResponse,
  } from "../auth/usersClient.ts";

  let user = $state<UserInfo | null>(getStoredUser());
  let token = $state<string | null>(getStoredAccessToken());
  let usersResponse = $state<UserListResponse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let successMsg = $state<string | null>(null);

  // Create form
  let showCreate = $state(false);
  let newEmail = $state("");
  let newUsername = $state("");
  let newPassword = $state("");
  let newRole = $state("viewer");
  let newIsActive = $state(true);
  let creating = $state(false);

  // Edit inline
  let editingId = $state<string | null>(null);
  let editUsername = $state("");
  let editRole = $state("viewer");
  let editIsActive = $state(true);
  let saving = $state(false);

  async function loadUsers() {
    if (!token) {
      loading = false;
      return;
    }
    loading = true;
    error = null;
    try {
      const u = await getMe();
      if (!u) {
        user = null;
        token = null;
        loading = false;
        return;
      }
      user = u;
      if (u.role !== "admin") {
        loading = false;
        return;
      }
      usersResponse = await listUsers(token!);
    } catch (err: unknown) {
      if (err instanceof Error) {
        error = err.message;
      } else {
        error = "Error desconocido";
      }
    } finally {
      loading = false;
    }
  }

  function startEdit(u: UserInfo) {
    editingId = u.id;
    editUsername = u.username ?? "";
    editRole = u.role;
    editIsActive = u.is_active;
  }

  function cancelEdit() {
    editingId = null;
  }

  async function saveEdit(u: UserInfo) {
    if (!token) return;
    saving = true;
    error = null;
    try {
      const updated = await updateUser(token, u.id, {
        username: editUsername || null,
        role: editRole,
        is_active: editIsActive,
      });
      if (usersResponse) {
        usersResponse.items = usersResponse.items.map((x) => (x.id === u.id ? updated : x));
        usersResponse = { ...usersResponse };
      }
      editingId = null;
      successMsg = `Usuario ${updated.email} actualizado`;
      setTimeout(() => (successMsg = null), 3000);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : "Error al actualizar";
    } finally {
      saving = false;
    }
  }

  async function handleActivate(u: UserInfo) {
    if (!token) return;
    error = null;
    try {
      const updated = await activateUser(token, u.id);
      if (usersResponse) {
        usersResponse.items = usersResponse.items.map((x) => (x.id === u.id ? updated : x));
        usersResponse = { ...usersResponse };
      }
      successMsg = `Usuario ${updated.email} activado`;
      setTimeout(() => (successMsg = null), 3000);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : "Error al activar";
    }
  }

  async function handleDeactivate(u: UserInfo) {
    if (!token) return;
    error = null;
    try {
      const updated = await deactivateUser(token, u.id);
      if (usersResponse) {
        usersResponse.items = usersResponse.items.map((x) => (x.id === u.id ? updated : x));
        usersResponse = { ...usersResponse };
      }
      successMsg = `Usuario ${updated.email} desactivado`;
      setTimeout(() => (successMsg = null), 3000);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : "Error al desactivar";
    }
  }

  async function handleCreate(e: Event) {
    e.preventDefault();
    if (!token) return;
    creating = true;
    error = null;
    try {
      const created = await createUser(token, {
        email: newEmail,
        username: newUsername || null,
        password: newPassword,
        role: newRole,
        is_active: newIsActive,
      });
      if (usersResponse) {
        usersResponse.items = [...usersResponse.items, created];
        usersResponse.total += 1;
        usersResponse = { ...usersResponse };
      }
      newEmail = "";
      newUsername = "";
      newPassword = "";
      newRole = "viewer";
      newIsActive = true;
      showCreate = false;
      successMsg = `Usuario ${created.email} creado`;
      setTimeout(() => (successMsg = null), 3000);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : "Error al crear";
    } finally {
      creating = false;
    }
  }

  async function handleLogout() {
    await logout();
    user = null;
    token = null;
    usersResponse = null;
  }

  // Bootstrap
  $effect(() => {
    loadUsers();
  });
</script>

<div class="card bg-base-100 w-full max-w-4xl shadow-xl">
  <div class="card-body">
    <h2 class="card-title">{BRAND.publicName}</h2>
    <p class="text-sm text-base-content/70">Administración de usuarios</p>

    {#if successMsg}
      <div class="alert alert-success text-sm">
        <span>{successMsg}</span>
      </div>
    {/if}
    {#if error}
      <div class="alert alert-error text-sm" role="alert">
        <span>{error}</span>
      </div>
    {/if}

    {#if !token}
      <div class="alert alert-info">
        <span>Debes iniciar sesión para administrar usuarios.</span>
      </div>
      <div class="card-actions mt-4">
        <a href={ROUTES.login} class="btn btn-primary">Iniciar sesión</a>
      </div>
    {:else if loading}
      <div class="flex items-center gap-2 py-8">
        <span class="loading loading-spinner loading-sm"></span>
        <span>Cargando usuarios…</span>
      </div>
    {:else if !user}
      <div class="alert alert-info">
        <span>Sesión no válida. <a href={ROUTES.login} class="link link-primary">Iniciar sesión</a></span>
      </div>
    {:else if user.role !== "admin"}
      <div class="alert alert-error">
        <span>No autorizado. Se requiere rol admin para administrar usuarios.</span>
      </div>
    {:else}
      <div class="flex items-center justify-between gap-4">
        <p class="text-sm">
          <span class="font-medium">{user.email}</span>
          <span class="badge badge-primary badge-sm ml-2">{user.role}</span>
        </p>
        <div class="flex gap-2">
          <button class="btn btn-sm" onclick={() => { showCreate = !showCreate; error = null; }}>
            {showCreate ? "Cancelar" : "Crear usuario"}
          </button>
          <button class="btn btn-ghost btn-sm" onclick={handleLogout}>Cerrar sesión</button>
        </div>
      </div>

      {#if showCreate}
        <form class="mt-4 rounded-box border p-4" onsubmit={handleCreate}>
          <h3 class="mb-3 font-bold">Nuevo usuario</h3>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="form-control">
              <span class="label-text">Email</span>
              <input type="email" class="input input-bordered input-sm mt-1" required bind:value={newEmail} disabled={creating} />
            </label>
            <label class="form-control">
              <span class="label-text">Username</span>
              <input type="text" class="input input-bordered input-sm mt-1" bind:value={newUsername} disabled={creating} />
            </label>
            <label class="form-control">
              <span class="label-text">Contraseña</span>
              <input type="password" class="input input-bordered input-sm mt-1" required minlength={8} bind:value={newPassword} disabled={creating} />
            </label>
            <label class="form-control">
              <span class="label-text">Rol</span>
              <select class="select select-bordered select-sm mt-1" bind:value={newRole} disabled={creating}>
                <option value="admin">admin</option>
                <option value="editor">editor</option>
                <option value="viewer">viewer</option>
              </select>
            </label>
            <label class="form-control">
              <span class="label-text">Activo</span>
              <input type="checkbox" class="toggle toggle-sm mt-2" bind:checked={newIsActive} disabled={creating} />
            </label>
          </div>
          <div class="mt-4">
            <button class="btn btn-primary btn-sm" type="submit" disabled={creating}>
              {#if creating}<span class="loading loading-spinner loading-xs"></span>{/if}
              Crear
            </button>
          </div>
        </form>
      {/if}

      {#if usersResponse}
        <div class="mt-6 overflow-x-auto">
          <table class="table table-zebra table-pin-rows table-sm">
            <thead>
              <tr>
                <th>Email</th>
                <th>Username</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Último acceso</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {#each usersResponse.items as u}
                <tr>
                  {#if editingId === u.id}
                    <td>{u.email}</td>
                    <td>
                      <input type="text" class="input input-bordered input-xs" bind:value={editUsername} disabled={saving} />
                    </td>
                    <td>
                      <select class="select select-bordered select-xs" bind:value={editRole} disabled={saving}>
                        <option value="admin">admin</option>
                        <option value="editor">editor</option>
                        <option value="viewer">viewer</option>
                      </select>
                    </td>
                    <td>
                      <input type="checkbox" class="toggle toggle-xs" bind:checked={editIsActive} disabled={saving} />
                    </td>
                    <td class="text-xs">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}</td>
                    <td>
                      <div class="flex gap-1">
                        <button class="btn btn-ghost btn-xs" onclick={() => saveEdit(u)} disabled={saving}>
                          {#if saving}<span class="loading loading-spinner loading-xs"></span>{/if}
                          Guardar
                        </button>
                        <button class="btn btn-ghost btn-xs" onclick={cancelEdit} disabled={saving}>Cancelar</button>
                      </div>
                    </td>
                  {:else}
                    <td class="font-medium">{u.email}</td>
                    <td>{u.username ?? "—"}</td>
                    <td><span class="badge badge-sm {u.role === 'admin' ? 'badge-primary' : u.role === 'editor' ? 'badge-info' : 'badge-ghost'}">{u.role}</span></td>
                    <td>
                      {#if u.is_active}
                        <span class="badge badge-success badge-sm">Activo</span>
                      {:else}
                        <span class="badge badge-error badge-sm">Inactivo</span>
                      {/if}
                    </td>
                    <td class="text-xs">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}</td>
                    <td>
                      <div class="flex gap-1">
                        <button class="btn btn-ghost btn-xs" onclick={() => startEdit(u)}>Editar</button>
                        {#if u.is_active}
                          <button class="btn btn-ghost btn-xs text-warning" onclick={() => handleDeactivate(u)}>Desactivar</button>
                        {:else}
                          <button class="btn btn-ghost btn-xs text-success" onclick={() => handleActivate(u)}>Activar</button>
                        {/if}
                      </div>
                    </td>
                  {/if}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <p class="mt-3 text-xs text-base-content/60">{usersResponse.total} usuario(s)</p>
      {/if}
    {/if}
  </div>
</div>
