import DOMPurify from "dompurify";
import { marked } from "marked";
import { detectLanguage, languageAttribute, normalizeDisplayText, textDirection } from "./textDirection.ts";

const ALLOWED_TAGS = ["h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "em", "blockquote", "hr", "code", "pre", "a", "table", "thead", "tbody", "tr", "th", "td"];
const FORBIDDEN_TAGS = ["script", "style", "img", "iframe", "object", "embed", "form", "input", "button", "svg", "math"];
const DIRECTIONAL_BLOCKS = "h1,h2,h3,h4,p,li,blockquote,th,td";

function isolateHebrewRuns(element: Element): void {
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  for (const node of nodes) {
    if (!/[\u0590-\u05ff]/u.test(node.data) || node.parentElement?.closest("bdi,code,pre")) continue;
    const parts = node.data.split(/([\u0590-\u05ff][\u0590-\u05ff\u0591-\u05c7\s'"״׳:;,.!?()§\d-]*)/gu).filter(Boolean);
    if (parts.length < 2) continue;
    const fragment = document.createDocumentFragment();
    for (const part of parts) {
      if (/[\u0590-\u05ff]/u.test(part)) {
        const bdi = document.createElement("bdi"); bdi.lang = "he"; bdi.dir = "rtl"; bdi.textContent = part; fragment.append(bdi);
      } else fragment.append(document.createTextNode(part));
    }
    node.replaceWith(fragment);
  }
}

function applyTrustedDirections(root: DocumentFragment): void {
  for (const element of root.querySelectorAll(DIRECTIONAL_BLOCKS)) {
    const text = normalizeDisplayText(element.textContent ?? "");
    const language = detectLanguage(text), lang = languageAttribute(text);
    element.setAttribute("dir", textDirection(text));
    if (lang) element.setAttribute("lang", lang); else element.removeAttribute("lang");
    if (language === "he") element.classList.add("research-hebrew-text");
    else if (language === "mixed") { element.classList.add("research-mixed-text"); isolateHebrewRuns(element); }
  }
}

export function renderSafeMarkdown(markdown: string): string {
  const displayMarkdown = markdown.replace(/\bpage\s*:\s*null\b/gi, "página no disponible");
  const parsed = marked.parse(displayMarkdown, { async: false, gfm: true, breaks: false });
  if (typeof DOMPurify.sanitize !== "function") return String(parsed).replace(/<[^>]*>/g, "");
  const clean = DOMPurify.sanitize(parsed, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ["href", "title"],
    FORBID_TAGS: FORBIDDEN_TAGS,
    FORBID_ATTR: ["style", "src", "srcdoc"],
    ALLOW_DATA_ATTR: false,
  });
  const template = document.createElement("template");
  template.innerHTML = clean;
  applyTrustedDirections(template.content);
  for (const link of template.content.querySelectorAll("a")) {
    const href = link.getAttribute("href") ?? "";
    let safe = false;
    try { const url = new URL(href, window.location.origin); safe = ["http:", "https:", "mailto:"].includes(url.protocol); } catch { safe = false; }
    if (!safe) link.removeAttribute("href");
    else if (/^https?:/i.test(href)) { link.target = "_blank"; link.rel = "noopener noreferrer"; }
  }
  return template.innerHTML;
}
