# Purpose

- These short books are for teaching my son Nicholas to love reading.
- So they're mostly about him doing fantastical things.
- Useful characters: mom; dad; his 1yo sister Mia; his same-age
  friends Linus and Kasim; and his older friends Kevin and Susie.

# Workflow

- Start by writing the contents of the book, as described below.
  Review the writing on your own before moving on.
- Then, write the "visual bible" for illustrations, as described
  below. Review the result on your own before moving on.
- Then, generate illustrations for each page, as described below.
  Don't review these; we're not aiming for a work of art here.
- Finally, assemble the HTML template, update the index page, review
  the final result, and deploy with `make`.
- The user can request changes in a follow-up, post-deploy, if needed.

# Writing

- Target a title page plus six content pages with 75-90 words total.
  Target 1-2 sentences per page, and roughly balance the number of
  words per page. Target 10-20 new words per book, compared to
  previous books.
- Nicholas is four years old. He reads letter by letter. Keep
  sentences short; 6-8 words is ideal.
- Keep words short and simple. Six letters and above are "long" words
  and need to be rare.
- Avoid: lower-case "b" and "d" (he mixes them up); dipthongs.
- Here is an example book:

  1. Title: `Nicholas At Moon Base Linus`; subtitle: `A moon home tale`.
  2. `Nicholas was on the Moon. He went to see Linus.`
  3. `Linus saw Nicholas. Linus said. “Come to my house!”`
  4. `They went to Linus's house. It was a moon base.`
  5. `The base had many domes. The domes had long tunnels.`
  6. `They went in. Linus had cake at home.`
  7. `They ate cake. They ate it together.`

# Art

- Write the book first, so it can be the source of truth. Treat the finished
  book as the source of truth: extract its title and the exact visible
  English reading text for every page, then use that text to derive each
  image's scene. Do not invent scenes that are not supported by the book.
- Create one fixed visual bible for each book. It must describe that book's
  recurring characters, proportions, palette, setting, and important props.
  Each page of a book gets the same visual bible (but books may
  differ). Here's an example visual bible:

```text
Book: Nicholas at Moon Base Linus.
Nicholas is a small four-year-old boy with peach skin, dark purple bowl-cut
hair, a coral-red suit, and a light-blue backpack. Linus is a small boy with
brown skin, short golden hair, a teal suit, and a light-blue backpack. Keep
both children as rounded simple figures with round heads, dot eyes, clear
full-body silhouettes, and these same designs on every page. The setting is a
Moon surface or a Moon-base interior: dark navy and lilac sky, pale moon
ground, cool blue glass domes, long blue tunnels, and warm yellow lights. No
adults and no other children.
```

- Use the following fixed style prompt, unchanged, for each image: You
  are illustrating a children's early-reader picture book. Use simple
  geometric shapes, flat colors with soft gradients, thick rounded
  dark navy outlines, sparse large readable forms, and colorful
  playful modern vector-like art. Make one clear scene with one simple
  action that matches each page. Use a portrait 3:4 aspect ratio.
  Leave the reading copy outside the image. Do not put any text,
  letters, numbers, labels, speech bubbles, logos, watermarks, extra
  characters, or tiny clutter in the illustration.
- Draw named friends fair-skinned, they are various combinations of
  white, asian, or mixed. Unnamed kids can be whatever race.
- For each page, combine the unchanged shared style prompt, that
  book's unchanged visual bible, and a scene section derived from that
  page's exact contents. Change only the page scene.
- For each page, pass the story prefix through the current page plus
  the current page's exact text. Do not include future page contents.
  This prevents later settings from leaking into early scenes.
- Generate one image per cover and content page with the same model
  and aspect ratio.
- General ages

# Code

- This directory is a standalone Git repository for code and instructions.
  Books (`/*.html`, including `index.html`), `art/`, and `book-data/` stay
  local and ignored. Adding or editing a book must not create a Git change.
  Never force-add these files, `.deploy/`, or credentials. See `README.md`.
- Always deploy with `make` after every change.
- Every book imports the shared `book.css` and `book.js` files. Keep the
  common layout, responsive rules, navigation, fullscreen controls, and
  Chinese-word mode in those shared files.
- Keep book-specific colors, font-size adjustments, and page copy
  backgrounds in CSS custom properties on the book or page elements. Keep
  each book's translation map in its `data-translations` attribute.
- `index.html` lists every book from most recent to least recent. A shared
  asset change does not make every book newer; preserve the books' content
  recency order when updating the index.
- For index word counts, count only visible English reading text: include
  the cover title and all `.story` text, but exclude `.subtitle` text,
  controls, accessibility labels, SVG art, and Chinese translations.
  Count punctuation-free English word tokens; contractions count as one
  word.
- Under every book title in `index.html`, include a "New words" block.
  Compute it by comparing that book's visible English reading tokens
  (cover title plus `.story` text) case-insensitively with the tokens in
  all older books listed below it. Exclude subtitles, controls,
  accessibility labels, SVG art, and Chinese translations. Keep
  contractions as one token, list each new word once, and preserve its
  first-appearance order in the book. When adding or changing a book,
  recompute its block and the blocks for newer books above it.
- When adding or changing a book, update its title and word count in
  `index.html`, validate the count against the book's title and story text,
  and run `make` so the index and shared assets are deployed too.
