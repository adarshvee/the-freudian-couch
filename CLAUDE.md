# The Freudian Couch — working notes for agents

A Hugo blog of book reviews, short stories, and personal essays.

## Author's voice / house style
- The author writes their own content and provides it ready. **Do not rewrite, paraphrase, or "improve" the prose.** Your job is structure, front matter, and mechanics — not editing their words.
- Any text *you* generate (meta `description`, image alt text, etc.) must match the voice of the story/essay it belongs to. The house style lives in the pieces themselves — read the actual post, not just other front matter. Descriptions are short, thematic, and understated (e.g. Moonshine: "A historical fiction about loyality, sacrifice and maternal love"), never a mechanical restatement of the writing prompt. Stay on the story's surface — a description must not reveal the twist, the ending, or which character turns out to matter (e.g. Brown: "A short story about interview anxieties and the desire to help others").

## Surface every judgment call you made
When you generate or decide anything the user didn't spell out — a meta description, a title style, tags, an alt text, where an image goes, which posts to relate — **call it out explicitly** as a decision for the user to review, don't bury it. Especially for author-facing copy like the meta `description`. The user should never have to discover a choice you made by reading the diff.

## Post conventions (see content/posts/2026/trinkets for the canonical template)
- Posts live in `content/posts/<year>/<slug>/index.md` with a co-located `featuredSmall.<ext>` image (this filename is what makes the thumbnail work).
- Front matter is TOML (`+++`): `title`, `url = "<year>/<mm>/<slug>"`, `date`, `description`, `tags`.
- Short-story titles use the pattern `"<Title> - A short story"`.
- Inline the featured image early in the body: `![alt](featuredSmall.<ext>)`.
- Short stories originally published elsewhere end with a `---` rule, then "This story was originally [published at …](url) in response to the prompt …".
- Close with a related shortcode: `{{< related >}} [A](/url/) · [B](/url/) · [C](/url/) {{< /related >}}`. Prefer recent thematically-linked posts; internal links are root-relative.
