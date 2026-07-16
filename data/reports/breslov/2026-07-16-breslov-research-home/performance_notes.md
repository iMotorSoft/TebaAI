# Performance notes

- Static HTML is produced for the public home; JavaScript is limited to the two interactive Svelte islands.
- Landscape variants are local WebP assets totaling approximately 470 KB across responsive representations; browsers select by `srcset`/`sizes`.
- Explicit image dimensions reserve layout space. Non-critical decoration is CSS only.
- No external image host, UI-library runtime, tracking script, or additional font download was introduced.
