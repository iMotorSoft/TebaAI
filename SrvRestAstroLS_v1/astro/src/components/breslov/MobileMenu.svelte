<script lang="ts">
  let { links }: { links: string[][] } = $props();
  let open = $state(false);
  function close() { open = false; }
</script>

<div class="mobile-menu">
  <button class="menu-toggle" type="button" aria-label="Abrir menú" aria-expanded={open} onclick={() => open = !open}>
    <span></span><span></span><span></span>
  </button>
  {#if open}
    <div class="mobile-menu-panel" id="mobile-navigation">
      <nav aria-label="Navegación móvil">
        {#each links as link}
          <a href={link[1]} onclick={close}>{link[0]}</a>
        {/each}
        <a class="mobile-login" href="/login" onclick={close}>Iniciar sesión</a>
      </nav>
    </div>
  {/if}
</div>
