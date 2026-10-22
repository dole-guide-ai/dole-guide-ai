"""청크 확인용 HTML 뷰어를 만듭니다. 서버 없이 파일을 브라우저로 열면 됩니다.

uv run python -m scripts.ingest.view_chunks
→ data/knowledge/chunks/viewer.html (data/ 아래라 git에 올라가지 않습니다)
"""

import json
from pathlib import Path

from scripts.ingest import chunk, paths
from scripts.ingest.fetch import save_text
from scripts.ingest.schemas import PolicyDetail

OUTPUT = paths.CHUNKS / "viewer.html"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _empty_sections() -> dict[str, list[str]]:
    """정책별 빈 목차(원문이 비어 청크가 없는 목차). 뷰어에서 함께 보여 줍니다."""
    empty = {}
    for path in (paths.WORK24_PROCESSED / "policies").glob("*.json"):
        detail = PolicyDetail.model_validate_json(path.read_text(encoding="utf-8"))
        empty[path.stem] = [s.original_title for s in detail.sections if not s.blocks]
    return empty


def build_html(catalog: list[dict], content: list[dict], faqs: list[dict], empty: dict) -> str:
    data = {
        "catalog": catalog,
        "content": content,
        "faqs": faqs,
        "empty": empty,
        "limits": {"min": chunk.MIN_TOKENS, "max": chunk.MAX_TOKENS},
    }
    # </script>로 스크립트가 끊기지 않게 "<"를 이스케이프합니다.
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return TEMPLATE.replace("__DATA__", payload)


def main() -> None:
    html = build_html(
        _jsonl(paths.POLICY_CATALOG_CHUNKS),
        _jsonl(paths.POLICY_CONTENT_CHUNKS),
        _jsonl(paths.FAQ_CHUNKS),
        _empty_sections(),
    )
    save_text(OUTPUT, html)
    print(f"뷰어 생성: {OUTPUT}\n브라우저로 열어 확인하세요.")


TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>청크 뷰어</title>
<style>
  :root { --bg:#f7f7f5; --card:#fff; --text:#1d1d1b; --muted:#6b6b66; --line:#e2e2dc;
          --accent:#2457c5; --warn:#b26a00; --bad:#c0392b; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#161615; --card:#21211f; --text:#ecece8; --muted:#a3a39c; --line:#34342f;
            --accent:#7aa2ff; --warn:#e0a040; --bad:#ff7b6b; }
  }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.6 system-ui, "Malgun Gothic", sans-serif;
         background:var(--bg); color:var(--text); }
  .layout { display:grid; grid-template-columns:300px 1fr; height:100vh; }
  aside { border-right:1px solid var(--line); overflow:auto; padding:12px; }
  main { overflow:auto; padding:20px 24px 60px; }
  input { width:100%; padding:8px 10px; border:1px solid var(--line); border-radius:6px;
          background:var(--card); color:var(--text); font:inherit; }
  .group { margin:14px 0 4px; font-size:12px; color:var(--muted); font-weight:600; }
  .item { display:block; width:100%; text-align:left; padding:6px 8px; border:0;
          border-radius:6px; background:none; color:inherit; font:inherit; cursor:pointer; }
  .item:hover { background:var(--line); }
  .item.on { background:var(--accent); color:#fff; }
  .item small { display:block; opacity:.7; font-size:12px; }
  h1 { font-size:22px; margin:0 0 4px; }
  h2 { font-size:16px; margin:28px 0 8px; padding-bottom:4px; border-bottom:1px solid var(--line); }
  .meta { color:var(--muted); font-size:13px; }
  .meta a { color:var(--accent); }
  .card { background:var(--card); border:1px solid var(--line); border-radius:8px;
          padding:12px 14px; margin:8px 0; }
  .card.catalog { border-left:4px solid var(--accent); }
  .tags { display:flex; flex-wrap:wrap; gap:6px; font-size:12px; margin-bottom:6px; }
  .tag { padding:1px 7px; border-radius:10px; background:var(--line); }
  .tag.small { color:var(--warn); } .tag.big { color:#fff; background:var(--bad); }
  .id { font-family:ui-monospace, Consolas, monospace; color:var(--muted); }
  pre { white-space:pre-wrap; word-break:break-word; margin:0; font:inherit; }
  .empty { color:var(--warn); font-size:13px; }
  .summary { display:flex; gap:16px; flex-wrap:wrap; margin:10px 0 0; font-size:13px; }
  @media (max-width: 760px) {
    .layout { grid-template-columns:1fr; height:auto; }
    aside { max-height:40vh; border-right:0; border-bottom:1px solid var(--line); }
    main { padding:16px; }
  }
</style>
</head>
<body>
<div class="layout">
  <aside>
    <input id="q" placeholder="정책명·FAQ 제목·본문 검색" autocomplete="off">
    <div id="list"></div>
  </aside>
  <main id="view"></main>
</div>
<script>
const D = __DATA__;
const $ = (s) => document.querySelector(s);
const ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ENTITIES[c]);
const tokens = (s) => s.replace(/\\s/g, "").length;

const policies = D.catalog.map((c) => ({
  kind: "policy", key: c.policy_id, name: c.metadata.policy_name, catalog: c,
  chunks: D.content.filter((x) => x.policy_id === c.policy_id),
}));
const faqs = [...new Map(D.faqs.map((f) => [f.faq_id, f])).keys()].map((id) => {
  const chunks = D.faqs.filter((f) => f.faq_id === id);
  return { kind: "faq", key: id, name: chunks[0].metadata.title, chunks };
});
let current = null;

function searchable(entry) {
  return (entry.name + " " + entry.chunks.map((c) => c.content).join(" ")).toLowerCase();
}

function renderList() {
  const q = $("#q").value.trim().toLowerCase();
  const hit = (e) => !q || searchable(e).includes(q);
  const block = (title, entries) => {
    const shown = entries.filter(hit);
    return `<div class="group">${title} (${shown.length})</div>` + shown.map((e) =>
      `<button class="item${current === e ? " on" : ""}"
         data-kind="${e.kind}" data-key="${esc(e.key)}">
         ${esc(e.name)}<small>${e.chunks.length}개 청크</small></button>`).join("");
  };
  $("#list").innerHTML = block("고용24 정책", policies) + block("1350 FAQ", faqs);
}

function card(c, extra = "") {
  const n = tokens(c.content);
  const size = n > D.limits.max ? "big" : n < D.limits.min ? "small" : "";
  return `<div class="card ${extra}">
    <div class="tags">
      <span class="tag">${esc(c.chunk_type)}</span>
      <span class="tag ${size}">${n}토큰</span>
      ${c.block_ids?.length ? `<span class="tag">블록 ${esc(c.block_ids.join(", "))}</span>` : ""}
      <span class="id">${esc(c.chunk_id)}</span>
    </div>
    <pre>${esc(c.content)}</pre>
  </div>`;
}

function show(entry) {
  current = entry;
  renderList();
  const m = entry.chunks[0]?.metadata ?? entry.catalog.metadata;
  let html = `<h1>${esc(entry.name)}</h1>
    <div class="meta"><a href="${esc(m.source_url)}" target="_blank" rel="noopener">원문 보기 ↗</a>
    · ${entry.kind === "policy"
        ? "최종 수정일 " + esc(m.last_modified ?? "-")
        : "작성일 " + esc(m.published_at)}
    · 청크 ${entry.chunks.length}개</div>`;
  if (entry.kind === "policy") {
    const empty = D.empty[entry.key] ?? [];
    const emptyNote = empty.length
      ? `<span class="empty">원문이 빈 목차: ${esc(empty.join(", "))}</span>`
      : "";
    html += `<div class="summary">
      <span>크기 기준: 목표 ${D.limits.min}~600, 최대 ${D.limits.max}토큰</span>${emptyNote}</div>`;
    html += `<h2>정책 탐색용 청크</h2>` + card(entry.catalog, "catalog");
    const sections = new Map();
    for (const c of entry.chunks) {
      const title = c.metadata.original_title;
      if (!sections.has(c.section_id)) sections.set(c.section_id, { title, list: [] });
      sections.get(c.section_id).list.push(c);
    }
    for (const s of sections.values()) {
      html += `<h2>${esc(s.title)} <span class="meta">(${s.list.length})</span></h2>`;
      html += s.list.sort((a, b) => a.sequence - b.sequence).map((c) => card(c)).join("");
    }
  } else {
    html += entry.chunks.map((c) => card(c)).join("");
  }
  $("#view").innerHTML = html;
  $("#view").scrollTop = 0;
}

$("#q").addEventListener("input", renderList);
$("#list").addEventListener("click", (e) => {
  const b = e.target.closest(".item");
  if (!b) return;
  const pool = b.dataset.kind === "policy" ? policies : faqs;
  show(pool.find((x) => x.key === b.dataset.key));
});
renderList();
if (policies.length) show(policies.find((p) => p.name.startsWith("실업급여")) ?? policies[0]);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
