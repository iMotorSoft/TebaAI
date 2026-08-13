<script lang="ts">
  import { onMount } from "svelte";
  import { getMe, getStoredAccessToken } from "../auth/authClient.ts";
  import { MODULES } from "../modules/moduleRegistry.ts";

  /**
   * Premium module selector modal, opened from the public navbar "Ingresar".
   *
   * Native `<dialog>` provides role=dialog + aria-modal + focus trap + Escape
   * (cancel) + focus restoration for free via `showModal()`. Module cards are
   * semantic links that reuse the same safe redirect logic as the Home section:
   * anonymous → /login?next=…, authenticated → destination directly.
   */
  let {
    triggerLabel,
    className = "",
    onOpen,
    onClose,
    hideTrigger = false,
    open = $bindable(false),
  }: {
    triggerLabel: string;
    className?: string;
    onOpen?: () => void;
    onClose?: () => void;
    hideTrigger?: boolean;
    open?: boolean;
  } = $props();

  let trigger!: HTMLButtonElement;
  let dialog!: HTMLDialogElement;
  let authenticated = $state(false);
  let hydrated = $state(false);

  onMount(async () => {
    hydrated = true;
    if (!getStoredAccessToken()) return;
    authenticated = Boolean(await getMe());
  });

  function hrefFor(destination: string): string {
    return authenticated
      ? destination
      : `/login?next=${encodeURIComponent(destination)}`;
  }

  function openModal() {
    onOpen?.();
    dialog.showModal();
    open = true;
  }

  function closeModal() {
    dialog.close();
    open = false;
  }

  function handleClose() {
    // Return focus to the trigger (or a caller-provided element) after any
    // close path (Escape/button/backdrop).
    onClose?.();
    trigger?.focus();
    open = false;
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === dialog) {
      dialog.close();
    }
  }

  /**
   * Manual focus trap. Native `<dialog>` keeps focus inside on most browsers,
   * but Chromium can leak a Tab to the body at the wrap boundary; this closes
   * that gap so Tab/Shift+Tab stay within the dialog.
   */
  function trapFocus(event: KeyboardEvent) {
    if (event.key !== "Tab") return;
    const focusable = Array.from(
      dialog.querySelectorAll<HTMLElement>(
        'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  // Controlled open/close from a parent (mobile menu "Ingresar").
  $effect(() => {
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  });
</script>

{#if !hideTrigger}
<button
  type="button"
  bind:this={trigger}
  class={className}
  onclick={openModal}
  aria-haspopup="dialog"
  disabled={!hydrated}
>
  {triggerLabel}<span aria-hidden="true">→</span>
</button>
{/if}

<dialog
  bind:this={dialog}
  class="module-modal"
  aria-label="¿Dónde querés ingresar?"
  onclose={handleClose}
  onclick={handleBackdropClick}
  onkeydown={trapFocus}
>
  <div class="module-modal-panel">
    <button
      type="button"
      class="module-modal-close"
      onclick={closeModal}
      aria-label="Cerrar"
    >
      <span aria-hidden="true">×</span>
    </button>

    <p class="module-modal-kicker">Breslov Research</p>
    <h2 class="module-modal-title">¿Dónde querés ingresar?</h2>
    <p class="module-modal-subtitle">Elegí el espacio de trabajo.</p>

    <div class="module-modal-grid">
      {#each MODULES as mod (mod.id)}
        <a class="module-modal-card" href={hrefFor(mod.destination)}>
          <h3>{mod.label}</h3>
          <p>{mod.description}</p>
          <span class="module-modal-cta">
            {mod.ctaLabel}<span aria-hidden="true">→</span>
          </span>
        </a>
      {/each}
    </div>
  </div>
</dialog>
