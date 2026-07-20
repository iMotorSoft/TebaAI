<script lang="ts">
  import { onMount } from "svelte";
  import { getMe, getStoredAccessToken } from "../auth/authClient.ts";

  let { loginLabel, researchLabel, className = "" }: { loginLabel: string; researchLabel: string; className?: string } = $props();
  let authenticated = $state(false);

  onMount(async () => {
    if (!getStoredAccessToken()) return;
    authenticated = Boolean(await getMe());
  });
</script>

<a class={className} href={authenticated ? "/research" : "/login"} data-session-access>
  {authenticated ? researchLabel : loginLabel}<span aria-hidden="true">→</span>
</a>
