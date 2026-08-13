<script lang="ts">
  import { onMount } from "svelte";
  import { getMe, getStoredAccessToken } from "../auth/authClient.ts";

  /**
   * Session-aware module entry. Anonymous users are routed to the login with
   * the intended destination preserved via a `next` query param; an
   * authenticated session links straight to the destination (the destination's
   * own guard is the authorization authority).
   */
  let {
    destination,
    loginLabel,
    authenticatedLabel,
    className = "",
  }: {
    destination: string;
    loginLabel: string;
    authenticatedLabel: string;
    className?: string;
  } = $props();

  let authenticated = $state(false);

  onMount(async () => {
    if (!getStoredAccessToken()) return;
    authenticated = Boolean(await getMe());
  });

  const href = $derived(
    authenticated
      ? destination
      : `/login?next=${encodeURIComponent(destination)}`,
  );
</script>

<a class={className} href={href} data-module-entry>
  {authenticated ? authenticatedLabel : loginLabel}<span aria-hidden="true">→</span>
</a>
