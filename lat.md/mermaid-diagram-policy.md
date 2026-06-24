# Mermaid Diagram Policy

Mermaid is the canonical source for TebaAI technical diagrams.

Rules:

- Store Mermaid source in Markdown or `.mmd` files tracked by Git.
- Treat SVG, PNG and Excalidraw files as optional derived artifacts.
- Do not install the full gstack `/diagram` workflow.
- Do not make TebaAI depend on gstack.
- If rendering becomes part of CI or release evidence, add a local versioned
  dependency instead of relying on a global tool.

The source diagram is the reviewable artifact. Renders are outputs.
