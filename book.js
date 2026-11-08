(() => {
  const pages = [...document.querySelectorAll('.page')];
  const dots = document.querySelector('.dots');
  const book = document.querySelector('.book');
  const prev = document.getElementById('prev');
  const next = document.getElementById('next');
  const fullscreenButton = document.getElementById('fullscreen');
  const chineseToggle = document.getElementById('chinese-toggle');
  const translations = JSON.parse(book.dataset.translations || '{}');
  const swipeThreshold = Number(book.dataset.swipeThreshold || 110);
  let current = 0;

  function setChineseMode(enabled) {
    book.classList.toggle('chinese-mode', enabled);
    chineseToggle.setAttribute('aria-pressed', String(enabled));
    chineseToggle.setAttribute('aria-label', enabled ? 'Disable Chinese word translations' : 'Enable Chinese word translations');
    chineseToggle.title = enabled ? 'Disable Chinese word translations' : 'Enable Chinese word translations';
    document.querySelectorAll('.word').forEach(word => {
      word.disabled = !enabled;
      if (!enabled) word.classList.remove('translated');
    });
  }

  function prepareChineseWords() {
    document.querySelectorAll('.copy h1, .copy .story, .copy .subtitle').forEach(container => {
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
      const textNodes = [];
      let node;
      while ((node = walker.nextNode())) textNodes.push(node);
      textNodes.forEach(textNode => {
        const fragment = document.createDocumentFragment();
        const text = textNode.nodeValue;
        const wordPattern = /[A-Za-z]+(?:'[A-Za-z]+)?/g;
        let lastIndex = 0;
        let match;
        while ((match = wordPattern.exec(text))) {
          fragment.append(text.slice(lastIndex, match.index));
          const wordText = match[0];
          const word = document.createElement('button');
          word.type = 'button';
          word.className = 'word';
          word.textContent = wordText;
          word.disabled = true;
          word.setAttribute('aria-label', `Show Chinese translation for ${wordText}`);
          const translation = document.createElement('span');
          translation.className = 'translation';
          translation.textContent = ` (${translations[wordText.toLowerCase()] || wordText})`;
          translation.setAttribute('aria-hidden', 'true');
          word.addEventListener('click', () => {
            const translated = word.classList.toggle('translated');
            translation.setAttribute('aria-hidden', String(!translated));
          });
          fragment.append(word, translation);
          lastIndex = wordPattern.lastIndex;
        }
        fragment.append(text.slice(lastIndex));
        textNode.replaceWith(fragment);
      });
    });
  }

  function showPage(index) {
    current = Math.max(0, Math.min(index, pages.length - 1));
    pages.forEach((page, pageIndex) => {
      const active = pageIndex === current;
      page.classList.toggle('active', active);
      page.setAttribute('aria-hidden', String(!active));
    });
    [...dots.children].forEach((dot, dotIndex) => dot.classList.toggle('active', dotIndex === current));
    prev.disabled = current === 0;
    next.disabled = current === pages.length - 1;
  }

  function updateFullscreenButton() {
    const active = document.fullscreenElement === book || document.webkitFullscreenElement === book;
    fullscreenButton.textContent = active ? '×' : '⛶';
    fullscreenButton.setAttribute('aria-label', active ? 'Exit full screen' : 'Enter full screen');
    fullscreenButton.title = active ? 'Exit full screen' : 'Enter full screen';
  }

  pages.forEach((_, index) => {
    const dot = document.createElement('span');
    dot.className = 'dot' + (index === 0 ? ' active' : '');
    dot.setAttribute('aria-label', `Page ${index + 1}`);
    dots.append(dot);
  });

  prepareChineseWords();
  showPage(0);
  chineseToggle.addEventListener('click', () => setChineseMode(chineseToggle.getAttribute('aria-pressed') !== 'true'));
  prev.addEventListener('click', () => showPage(current - 1));
  next.addEventListener('click', () => showPage(current + 1));
  document.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft') showPage(current - 1);
    if (event.key === 'ArrowRight' || event.key === ' ') showPage(current + 1);
  });
  fullscreenButton.addEventListener('click', async () => {
    const fullscreenElement = document.fullscreenElement || document.webkitFullscreenElement;
    const exitFullscreen = document.exitFullscreen || document.webkitExitFullscreen;
    const requestFullscreen = book.requestFullscreen || book.webkitRequestFullscreen;
    if (fullscreenElement && exitFullscreen) await exitFullscreen.call(document);
    else if (requestFullscreen) await requestFullscreen.call(book);
  });
  document.addEventListener('fullscreenchange', updateFullscreenButton);
  document.addEventListener('webkitfullscreenchange', updateFullscreenButton);

  let touchStartX = null;
  book.addEventListener('touchstart', event => {
    if (event.target.closest('button')) { touchStartX = null; return; }
    touchStartX = event.changedTouches[0].screenX;
  }, { passive: true });
  book.addEventListener('touchend', event => {
    if (touchStartX === null) return;
    const distance = event.changedTouches[0].screenX - touchStartX;
    if (Math.abs(distance) > swipeThreshold) showPage(current + (distance < 0 ? 1 : -1));
    touchStartX = null;
  }, { passive: true });
  updateFullscreenButton();
})();
