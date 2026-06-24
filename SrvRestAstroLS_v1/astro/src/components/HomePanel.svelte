<script lang="ts">
  let apiBase = $state(
    import.meta.env.PUBLIC_TEBAAI_API_BASE_URL ?? "http://127.0.0.1:7008",
  );
</script>

<section class="home-panel" aria-labelledby="home-title">
  <p class="eyebrow">Generic content platform</p>
  <h1 id="home-title">Teba AI</h1>
  <p class="summary">
    Bootstrap inicial para una plataforma de contenidos con backend Litestar y
    frontend Astro + Svelte 5.
  </p>
  <dl>
    <div>
      <dt>Backend</dt>
      <dd>{apiBase}</dd>
    </div>
    <div>
      <dt>Vertical inicial</dt>
      <dd>Breslov, en una fase posterior</dd>
    </div>
  </dl>
</section>

<style>
  .home-panel {
    width: min(680px, 100%);
    padding: 32px;
    border: 1px solid #d8dee5;
    border-radius: 8px;
    background: #ffffff;
    box-shadow: 0 18px 48px rgba(16, 24, 40, 0.08);
  }

  .eyebrow {
    margin: 0 0 8px;
    color: #456173;
    font-size: 0.875rem;
    font-weight: 700;
    letter-spacing: 0;
    text-transform: uppercase;
  }

  h1 {
    margin: 0;
    font-size: 2.75rem;
    line-height: 1.05;
    letter-spacing: 0;
  }

  .summary {
    max-width: 56ch;
    margin: 16px 0 24px;
    color: #405261;
    font-size: 1.05rem;
    line-height: 1.6;
  }

  dl {
    display: grid;
    gap: 12px;
    margin: 0;
  }

  dl > div {
    display: grid;
    gap: 4px;
    padding: 12px 0;
    border-top: 1px solid #e6ebef;
  }

  dt {
    color: #586b7a;
    font-size: 0.875rem;
    font-weight: 700;
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
</style>
