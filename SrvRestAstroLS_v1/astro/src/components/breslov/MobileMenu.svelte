<script lang="ts">
  import { onMount } from "svelte";
  import ModuleModal from "./ModuleModal.svelte";

  let { links }: { links: string[][] } = $props();
  let open = $state(false);
  let modalOpen = $state(false);
  let hydrated = $state(false);
  let menuButton: HTMLButtonElement;

  onMount(() => {
    hydrated = true;
  });

  function close(restoreFocus = false) {
    open = false;
    if (restoreFocus) queueMicrotask(() => menuButton?.focus());
  }

  function openIngresarModal() {
    close();
    modalOpen = true;
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
  <button bind:this={menuButton} class="menu-toggle" type="button" aria-label="Abrir menú" aria-controls="mobile-navigation" aria-expanded={open} disabled={!hydrated} onclick={() => open = !open}>
    <span></span><span></span><span></span>
  </button>
  {#if open}
    <div class="mobile-menu-panel" id="mobile-navigation">
      <nav aria-label="Navegación móvil">
        {#each links as link}
          <a href={link[1]} onclick={close}>{link[0]}</a>
        {/each}
        <button type="button" class="mobile-login" aria-haspopup="dialog" onclick={openIngresarModal}>
          Ingresar<span aria-hidden="true">→</span>
        </button>
        <a class="mobile-request" href="/request-access" onclick={close}>Solicitar acceso</a>
      </nav>
    </div>
  {/if}
  <ModuleModal bind:open={modalOpen} hideTrigger triggerLabel="Ingresar" className="mobile-login" onClose={() => menuButton?.focus()} />
</div>
