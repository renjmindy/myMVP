---
name: storytelling-viz-publish
description: Publish a finished self-contained visualization artifact (index.html) to a Jekyll/GitHub Pages site as a responsive iframe embed with a draft markdown post. Use this skill when the user has a confirmed Jekyll/GitHub Pages target and asks to publish, embed, or post a visualization that already exists as a local index.html/preview.html pair (e.g. produced by the storytelling-viz skill).
---

# Storytelling Viz — Publish

Use this skill when the task is only about taking an already-finished visualization
artifact and getting it onto a Jekyll/GitHub Pages site. Choosing, building, or
refining the chart itself is out of scope here — that belongs to a viz-generation
skill such as `storytelling-viz`. Keeping these as two separate skills means either
can be reused on its own: a chart built any other way can still be published with
this skill, and a chart built with `storytelling-viz` can be delivered locally
without ever touching a site repo.

## Skill Promise

Given a finished `index.html` (and optionally `preview.html`) and a confirmed site
target, produce:

- the visualization copied into the site's asset path
- a responsive iframe embed snippet
- a draft markdown post ready to review

Never guess the site's repo path, posts directory, or front-matter schema, and
never commit or push without explicit confirmation.

## When to Use This Skill

Use this skill when the user:

- has a finished local visualization artifact (`index.html`, ideally with a
  `preview.html` review wrapper) and a real Jekyll/GitHub Pages site to publish it to
- asks to "publish," "embed," or "post" a visualization to their site or blog
- wants a markdown post drafted around an existing chart

Do not use this skill when:

- the visualization doesn't exist yet — build it first with a viz-generation
  skill (`storytelling-viz` or equivalent), then come back to this one
- the target site is not Jekyll/GitHub Pages — the asset-path and front-matter
  conventions here are specific to that stack; ask before assuming it transfers
- no site repo path or URL has been given — stop and ask rather than proceeding

## Fast Path

1. Confirm the artifact: locate the finished `index.html` (and `preview.html` if
   present), and the headline, takeaway, insight bullets, and linked data source
   that go with it. If any of these are missing, ask rather than inventing them.
2. Confirm the site: repo path or URL, the posts directory (commonly `_posts/`)
   and its filename convention (commonly `YYYY-MM-DD-title.md`), the assets
   directory convention (commonly `assets/viz/<slug>/`), and the front-matter
   schema — read one existing post from the repo if available rather than
   guessing any of this.
3. Copy the artifact into the site's asset path and draft the embed + post (see
   Delivery Pattern below).
4. Show the user the planned changes — files to add, their paths, and the full
   post draft — before writing anything into the site repo.
5. Only stage, commit, or push if the user explicitly confirms; this follows
   the same git-safety expectations as any other repo change (no `--no-verify`,
   no force operations, confirm before anything that touches shared/remote state).

## Delivery Pattern

The most stable pattern for a static Jekyll site is: a standalone self-contained
HTML visualization, embedded via a responsive iframe.

1. Copy the finished `index.html` (unchanged) into the site repo at
   `assets/viz/<slug>/index.html`, where `<slug>` matches the artifact folder
   name already chosen when the chart was built.
2. Do not copy `preview.html` into the site — it is a local review wrapper, not
   publish output. Its editorial framing (headline, deck, notes) moves into the
   markdown post body instead.
3. Embed with a responsive iframe that listens for `postMessage` height
   reporting (the chart should already emit this — see below):

   ```html
   <div class="viz-embed">
     <iframe id="viz-frame" src="/assets/viz/<slug>/index.html"
             title="<chart title>" loading="lazy" style="height:780px"></iframe>
   </div>
   <script>
     window.addEventListener("message", (event) => {
       if (!event.data || event.data.type !== "viz-height") return;
       const frame = document.getElementById("viz-frame");
       if (!frame) return;
       const h = Math.max(420, Math.min(1400, Number(event.data.height) || 780));
       if (Math.abs(frame.offsetHeight - h) > 6) frame.style.height = `${h}px`;
     });
   </script>
   ```

   The inline fallback height keeps first paint from collapsing before the
   resize message arrives. If the source `index.html` does not already report
   its height via `postMessage`, note that as a caveat rather than silently
   shipping a fixed-height embed that may clip or leave dead space.

## Markdown Post Structure

Keep the post short — it frames the chart, it doesn't repeat it:

- Front matter: match whatever the site's existing posts use (layout, date,
  tags) — confirm from a real example rather than inventing a schema.
- One short intro: the same headline + one-sentence takeaway used in the
  source `preview.html`, not chart-mechanics language.
- The iframe embed.
- 2-3 insight bullets, carried over from the source artifact.
- A source line with the linked data source — mandatory, must carry through
  from the source artifact into the published post, not just live in the
  local files.

## Non-Negotiable Tests

- `Fidelity test`: the post's headline, takeaway, and caveats must match what
  the source artifact actually says — this skill drafts the publish wrapper,
  it does not re-interpret or embellish the underlying analysis.
- `No-guess test`: repo path, posts directory, asset path, and front-matter
  fields all come from the user or a real example post, never invented.
- `Confirm-before-write test`: the planned file changes are shown to the user
  before anything is written into the site repo, and nothing is committed or
  pushed without explicit confirmation.

## Final Quality Check

Before delivery, verify:

- the copied `index.html` still renders standalone (open it directly, not just
  inside the iframe) and still reports height via `postMessage` if it did before
- the draft post's front matter matches the site's existing convention
- the embed snippet uses the confirmed asset path, not a placeholder
- the data source is explicitly linked in the published post
- no repo changes (add/commit/push) happened without the user's explicit go-ahead
