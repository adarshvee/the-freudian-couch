---
name: goodreads-post
description: Converts an existing post from this blog into Goodreads-ready HTML, printed inline for the user to copy into Goodreads' review or blog box. Use when the user says "convert this for Goodreads", "/goodreads-post <slug>", "put the McQueen review on Goodreads", or names a post and mentions Goodreads. The input is always a post already in content/posts/ — never an external file. The author's prose is copied verbatim; only markup is transformed.
---

You convert a post that already lives in this repo into HTML that Goodreads accepts, and **print it inline in the conversation** for the user to copy-paste. You do not write a file, and you do not touch `content/`.

The author's words are not yours to change. You are transforming markup and nothing else — no rewording, no tightening, no fixing what looks like a typo.

## 1. Resolve the post

The argument may be a slug (`faces-in-the-flame`), a path, a title, or nothing at all.

- Slug or title → `ls content/posts/2026/` and the older flat `content/posts/*.md`, then grep titles: `grep -l -i "<words>" content/posts/*/*/index.md content/posts/*.md`.
- Nothing given → if the conversation already names a post, use it; otherwise ask which one.
- More than one plausible match → ask, don't guess.

Read the whole file before converting.

## 2. Work out the canonical URL

From the front matter `url` value and `baseURL = "https://www.thefreudiancouch.com/"` in `config/_default/hugo.toml`:

- `url = "2026/07/faces-in-the-flame-mcqueen"` → `https://www.thefreudiancouch.com/2026/07/faces-in-the-flame-mcqueen/` (**add the trailing slash**)
- `url = "2025/12/covenant-of-water.html"` → `https://www.thefreudiancouch.com/2025/12/covenant-of-water.html` (**no trailing slash** — Blogger-era URLs end in `.html`)

The featured image resolves the same way: `<canonical>featuredSmall.jpg` for the slash form.

## 3. Decide which shape of post this is

Ask if it is genuinely unclear; otherwise infer and say which you chose.

- **Book review** (tags include `Review` / `Book Review`) → goes in Goodreads' review box. **Do not repeat the title** — Goodreads already shows the book above the review.
- **Short story or essay** → goes in a Goodreads blog post or writing entry. Open with the title in `<b>`, since nothing else supplies it.

## 4. Convert the markup

Goodreads allows only: `<a>`, `<img>`, `<b>`, `<i>`, `<u>`, `<s>`, `<pre>`, `<blockquote>`, `<p>`, `<spoiler>`, plus `[book: Title]` and `[author: Name]`. Everything else is stripped or shown as literal text. Tags must nest properly — `<i><b>x</b></i>`, never `<i><b>x</i></b>`.

| In the post | In the Goodreads output |
|---|---|
| Front matter (`+++` block) | drop entirely |
| `**bold**` | `<b>bold</b>` |
| `*italic*` | `<i>italic</i>` |
| `***both***` | `<b><i>both</i></b>` |
| `## Heading` / `### Heading` | `<p><b>Heading</b></p>` — Goodreads has no headings |
| `> quote` | `<blockquote>quote</blockquote>` |
| `[text](url)` | `<a href="url">text</a>` |
| `[text](/2026/06/trinkets/)` | absolute: `<a href="https://www.thefreudiancouch.com/2026/06/trinkets/">text</a>` |
| `![alt](featuredSmall.jpg)` | `<img src="<canonical>featuredSmall.jpg" width="400" alt="alt"/>` |
| trailing two spaces (line break) | `<br/>` inside the same `<p>` |
| `---` horizontal rule | drop it; the paragraph break carries the beat |
| `{{< related >}} … {{< /related >}}` | drop it — it is blog navigation, not part of the piece |
| any other `{{< shortcode >}}` | drop the wrapper, keep the text inside if there is any |

**Unescape Google Docs backslashes.** These posts carry `\-`, `\!`, `\.`, `\[h\]` and similar from the author's drafting tool. Markdown eats the backslash; Goodreads does not, so `\-` would show up literally. Strip the backslash from every escaped punctuation mark. This is the single most common way this conversion goes wrong — check the output for stray `\` before printing.

Leave curly quotes, em dashes, and the author's spelling exactly as they are.

**Paragraphs:** wrap each in `<p>…</p>` and put them on consecutive lines with **no blank line between them**. Goodreads also converts newlines to breaks, so blank lines between `<p>` blocks come out double-spaced.

**Images:** `width` must be 0–400 and `height` 0–1000. Use `width="400"` and omit `height` so the aspect ratio holds. Keep the post's own alt text.

## 5. Goodreads-only additions

- **`[book: …]` and `[author: …]`** — on a book review, link *other* books and authors the post mentions on first mention only (e.g. `[book: Olive Kitteridge]` and `[author: Elizabeth Strout]`). Do not link the book being reviewed; Goodreads already shows it. The bare form lets Goodreads pick the match, which is occasionally the wrong edition — always list every one of these in your judgment-call report so the user can check them in preview.
  - **A name the post spells differently from Goodreads' catalogue needs the user's say-so.** The post says "Alistair McLean"; Goodreads files him as "Alistair MacLean", and the misspelt tag won't resolve. Respelling it is not a free fix — the tag *displays* the name you type, so it changes the author's visible text. Point out the mismatch and ask; don't respell on your own initiative.
  - Don't tag a title that sits inside `**bold**` in the source — the tag replaces the bold with a link and flattens a typographic run the author chose. Prefer a later unbolded mention; if there isn't one, skip it and say so.
- **`<spoiler>`** — **offer, don't apply.** On the blog a twist sits behind a click; on Goodreads it faces people deciding whether to read the book, so a passage giving away an ending, a twist, a death, or a concealed relationship is worth raising. But how much to give away is the author's call, always. Name the specific passages you'd wrap and ask.
  When the user says yes:
  - Wrap **at sentence or passage level, never whole paragraphs.** The reviewer's argument is the point of the review, and hiding a whole paragraph usually buries the thesis along with the reveal. Hide the concrete reveal; leave the reasoning visible.
  - Watch for a reveal that gets **restated later in the open** — spoilering one mention and not its echo protects nothing.
  - Keep each `<spoiler>` opened and closed inside its own `<p>`, and flag any sentence left pointing at hidden text so the user can check the seam.

## 6. The attribution line — always last

Close every conversion with, as the final line:

```html
<p><i>This review was originally posted at <a href="https://www.thefreudiancouch.com/2026/07/faces-in-the-flame-mcqueen/">The Freudian Couch</a>.</i></p>
```

Use "review" for book reviews, "story" for short stories, "post" for essays. If the post already ends with an originally-published-elsewhere note (ProWritersRoom and the like), keep that note **and** add this line after it — they credit different things.

## 7. Print it

Output the finished HTML in one fenced ```html block so the user can copy it whole. Nothing before it but a one-line note of what you converted.

Then, **below the block, list the judgment calls you made** — the house rule in `CLAUDE.md` applies here as much as anywhere:

- every `[book: …]` / `[author: …]` you inserted, and any name whose spelling doesn't match Goodreads' catalogue
- passages you think warrant `<spoiler>`, offered for the user to accept or decline
- anything you dropped (related shortcode, horizontal rules, unsupported markup)
- escapes you unescaped, where the post had them
- any place the source markup was ambiguous and you picked a reading

**Don't report the routine derivations** — which file the slug resolved to, how you built the canonical URL, review-box-vs-blog-post and the title line that follows from it. Those are mechanics, not decisions, and the user has already signed off on them. State them only when something was genuinely unusual or you had to guess.

Offer to adjust and reprint. Never write the HTML to a file unless the user asks.
