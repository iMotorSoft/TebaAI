<script lang="ts">
  import { onMount } from "svelte";
  import { getMe, getStoredAccessToken } from "../auth/authClient.ts";

  let { links }: { links: string[][] } = $props();
  let open = $state(false);
  let authenticated = $state(false);
  let menuButton: HTMLButtonElement;

  onMount(async () => {
    if (!getStoredAccessToken()) return;
    authenticated = Boolean(await getMe());
  });

  function close(restoreFocus = false) {
    open = false;
    if (restoreFocus) queueMicrotask(() => menuButton?.focus());
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape" && open) {
      event.preventDefault();
      close(true);
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="mobile-menu">
  <button bind:this={menuButton} class="menu-toggle" type="button" aria-label="Abrir menú" aria-controls="mobile-navigation" aria-expanded={open} onclick={() => open = !open}>
    <span></span><span></span><span></span>
  </button>
  {#if open}
    <div class="mobile-menu-panel" id="mobile-navigation">
      <nav aria-label="Navegación móvil">
        {#each links as link}
          <a href={link[1]} onclick={close}>{link[0]}</a>
        {/each}
        <a class="mobile-login" href={authenticated ? "/research" : "/login"} onclick={close}>{authenticated ? "Abrir investigación" : "Ingresar"}</a>
        <a class="mobile-request" href="/request-access" onclick={close}>Solicitar acceso</a>
      </nav>
    </div>
  {/if}
</div>
