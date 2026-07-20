<script lang="ts">
  let open = $state(false);
  let locale = $state("ES");
  let fallbackNotice = $state("");
  const choices = ["ES", "EN", "HE"];
  function select(next: string) {
    locale = next;
    open = false;
    fallbackNotice = next === "ES" ? "Interfaz disponible en español." : "La interfaz se mantiene en español; las fuentes y consultas admiten el idioma seleccionado.";
  }
</script>

<div class="language-picker">
  <button type="button" class="language-trigger" aria-label="Idiomas disponibles" aria-expanded={open} onclick={() => open = !open}>
    <span aria-hidden="true">◎</span>{locale}<span aria-hidden="true">⌄</span>
  </button>
  {#if open}
    <div class="language-options" role="menu">
      {#each choices as choice}
        <button role="menuitem" type="button" aria-current={choice === locale ? "true" : undefined} onclick={() => select(choice)}>{choice}</button>
      {/each}
    </div>
  {/if}
  {#if fallbackNotice}<p class="language-fallback" role="status">{fallbackNotice}</p>{/if}
</div>
