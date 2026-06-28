 <script lang="ts">
  import { BRAND, ROUTES } from "../global.js";
  import { getStoredUser, getStoredAccessToken, getMe } from "../auth/authClient.ts";
  import { searchLibrary, sanitizeHighlighted, type SearchRequest, type SearchResult } from "./librarySearchClient.ts";

  let token = $state<string | null>(getStoredAccessToken());
  let user = $state(getStoredUser());

  // Search form
  let query = $state("");
  let mode = $state<"auto" | "fts" | "phrase" | "trigram">("auto");
  let language = $state<"es" | "en" | "he">("es");
  let topK = $state(10);
  let collection = $state("breslov");

  let loading = $state(false);
  let error = $state<string | null>(null);
  let results = $state<SearchResult[]>([]);
  let total = $state(0);
  let lastQuery = $state("");

  async function handleSearch(e: Event) {
    e.preventDefault();
    if (!query.trim() || !token) return;

    loading = true;
    error = null;
    results = [];
    total = 0;
    lastQuery = query;

    try {
      const req: SearchRequest = {
        collection,
        query: query.trim(),
        mode,
        top_k: topK,
        language,
      };
      const resp = await searchLibrary(token, req);
      results = resp.results;
      total = resp.total;
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.message.includes("401") || err.message.includes("403")) {
          token = null;
          user = null;
          error = "Sesión expirada. Inicia sesión nuevamente.";
        } else {
          error = err.message;
        }
      } else {
        error = "Error al buscar";
      }
    } finally {
      loading = false;
    }
  }

  async function handleVerifySession() {
    const u = await getMe();
    if (u) {
      user = u;
      token = getStoredAccessToken();
    } else {
      token = null;
      user = null;
    }
  }
</script>

<div class="card bg-base-100 w-full max-w-4xl shadow-xl">
  <div class="card-body">
    <h2 class="card-title">{BRAND.publicName}</h2>
    <p class="text-sm text-base-content/70">Búsqueda bibliográfica</p>

    {#if !token}
      <div class="alert alert-info mt-4">
        <span>Necesitás iniciar sesión para buscar en la biblioteca.</span>
      </div>
      <div class="card-actions mt-4">
        <a href={ROUTES.login} class="btn btn-primary">Iniciar sesión</a>
      </div>
    {:else}
      <form class="mt-4" onsubmit={handleSearch}>
        <div class="flex flex-wrap gap-3 items-end">
          <label class="form-control flex-1 min-w-[200px]">
            <span class="label-text">Búsqueda</span>
            <input
              type="text"
              class="input input-bordered w-full"
              placeholder="Palabra o frase…"
              bind:value={query}
              disabled={loading}
            />
          </label>
          <label class="form-control w-28">
            <span class="label-text">Modo</span>
            <select class="select select-bordered" bind:value={mode} disabled={loading}>
              <option value="auto">auto</option>
              <option value="fts">fts</option>
              <option value="phrase">phrase</option>
              <option value="trigram">trigram</option>
            </select>
          </label>
          <label class="form-control w-24">
            <span class="label-text">Idioma</span>
            <select class="select select-bordered" bind:value={language} disabled={loading}>
              <option value="es">es</option>
              <option value="en">en</option>
              <option value="he">he</option>
            </select>
          </label>
          <label class="form-control w-20">
            <span class="label-text">Top K</span>
            <input type="number" class="input input-bordered" bind:value={topK} min="1" max="50" disabled={loading} />
          </label>
          <button class="btn btn-primary" type="submit" disabled={loading || !query.trim()}>
            {#if loading}
              <span class="loading loading-spinner loading-sm"></span>
            {/if}
            Buscar
          </button>
        </div>
      </form>

      {#if error}
        <div class="alert alert-error text-sm mt-4" role="alert">
          <span>{error}</span>
          {#if error.includes("Sesión")}
            <a href={ROUTES.login} class="link link-primary ml-2">Iniciar sesión</a>
          {/if}
        </div>
      {/if}

      {#if !loading && lastQuery && results.length === 0 && !error}
        <div class="alert mt-4">
          <span>Sin resultados para "{lastQuery}".</span>
        </div>
      {/if}

      {#if results.length > 0}
        <p class="mt-4 text-sm text-base-content/60">
          {total} resultado(s) para "{lastQuery}" en colección "{collection}"
        </p>
        <div class="mt-2 space-y-4">
          {#each results as r}
            <div class="rounded-box border p-4">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <h3 class="font-bold">{r.document_title}</h3>
                  {#if r.author}
                    <p class="text-xs text-base-content/60">{r.author}</p>
                  {/if}
                </div>
                <span class="badge badge-sm {r.match_type === 'fts' ? 'badge-primary' : r.match_type === 'phrase' ? 'badge-info' : 'badge-ghost'}">{r.match_type}</span>
              </div>
              <div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-base-content/50">
                <span>Chunk #{r.chunk_index}</span>
                {#if r.chapter}<span>Capítulo: {r.chapter}</span>{/if}
                {#if r.section}<span>Sección: {r.section}</span>{/if}
                {#if r.page_start}<span>Página: {r.page_start}{#if r.page_end}–{r.page_end}{/if}</span>{/if}
                {#if r.rank != null}<span>Score: {r.rank}</span>{/if}
              </div>
              <div class="mt-3 text-sm leading-relaxed">
                {#if r.highlighted_excerpt}
                  <!-- svelte-ignore a11y_no_nonstandard_sanitize -->
                  <div class="prose prose-sm max-w-none">{@html sanitizeHighlighted(r.highlighted_excerpt)}</div>
                {:else if r.plain_excerpt}
                  <p>{r.plain_excerpt}</p>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  </div>
</div>
