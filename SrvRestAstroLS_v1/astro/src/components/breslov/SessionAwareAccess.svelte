<script lang="ts">
  import { onMount } from "svelte";
  import { getMe, getStoredAccessToken } from "../auth/authClient.ts";

  let {
    loginLabel,
    researchLabel,
    className = "",
    next = "",
  }: {
    loginLabel: string;
    researchLabel: string;
    className?: string;
    next?: string;
  } = $props();
  let authenticated = $state(false);

  onMount(async () => {
    if (!getStoredAccessToken()) return;
    authenticated = Boolean(await getMe());
  });

  const href = $derived(
    authenticated
      ? (next || "/research")
      : (next ? `/login?next=${encodeURIComponent(next)}` : "/login"),
  );
</script>

<a class={className} href={href} data-session-access>
  {authenticated ? researchLabel : loginLabel}<span aria-hidden="true">→</span>
</a>
