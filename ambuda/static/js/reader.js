/* global Alpine */

/**
 * Application code for our Sanskrit reading environment.
 *
 * Our reading environment displays Sanskrit text with various rich features:
 *
 * - script, font size, and basic layout preferences
 * - padaccheda with word-by-word parse data
 * - dictionary search across a variety of standard dictionaries
 *
 *
 * # Design
 *
 * The reader is essentialy a single-page application (SPA) implemented in
 * Alpine. Certain components, such as text blocks and dictionary entries,
 * are rendered on the server and returned as HTML blobs.
 *
 *
 * # Technical terms
 *
 * - mula: the original verse (mūlam)
 * - slug: human-readable ID that appears in the URL.
 */

import { $ } from './core.ts';
import Routes from './routes';

export function getBlockSlug(blockID) {
  // Slice to remove text XML id.
  return blockID.split('.').slice(1).join('.');
}

/**
 * Split Devanagari text into aksharas (syllabic units).
 *
 * An akshara consists of a base character (consonant or vowel) followed by
 * any combining marks (nukta, vowel signs, virama, anusvara, visarga, etc.).
 *
 * @param {string} text - Input text (may contain both Devanagari and non-Devanagari)
 * @returns {string[]} Array of strings, each representing either an akshara or a single character
 */
function toAksharas(text) {
  const aksharas = [];
  // Match Devanagari aksharas: base character + combining marks
  // Base characters: U+0900-U+0963 (vowels, consonants, etc.), U+0970-U+097F
  // Combining marks: U+093C-U+094F (nukta, vowel signs, virama), U+0951-U+0954, U+0962-U+0963
  const aksharaRegex = /[\u0900-\u0963\u0970-\u097F][\u093C-\u094F\u0951-\u0954\u0962-\u0963]*/g;
  let lastIndex = 0;
  let match = aksharaRegex.exec(text);

  while (match !== null) {
    // Add any non-Devanagari characters before this akshara
    for (let i = lastIndex; i < match.index; i += 1) {
      aksharas.push(text[i]);
    }

    // Add the akshara
    aksharas.push(match[0]);
    lastIndex = match.index + match[0].length;
    match = aksharaRegex.exec(text);
  }

  // Add any remaining characters
  for (let i = lastIndex; i < text.length; i += 1) {
    aksharas.push(text[i]);
  }

  return aksharas;
}

const READER_CONFIG_KEY = 'reader';

export default () => ({

  // User settings
  // -------------
  // Persistent user-specific data that we store in localStorage.

  // Text size for body text.
  fontSize: 'md:text-xl',
  textWidth: 'md:max-w-xl',
  // The dictionary sources to use when fetching.
  dictSources: ['mw'],
  sidebarWidth: 512,
  userScript: 'devanagari',

  // Server data
  // -----------
  // Text or dictionary data fetched from the server.

  data: {
    text_title: null,
    section_title: null,
    section_slug: null,
    blocks: [],
    prev_url: null,
    next_url: null,
  },

  // The current dictionary response.
  dictionaryResponse: null,
  // Analysis of a word clicked by the user.
  wordAnalysis: { form: null, lemma: null, parse: null },
  analyzeData: { blockSlug: null, words: [], error: null },

  // Transient data
  // --------------
  // Internal application data that manages the application state.

  // If true, show the sidebar.
  showSidebar: false,
  sidebarTab: null,
  showSettings: false,
  // Text in the dictionary search field.
  dictQuery: '',
  // If true, show the dictionary selection widget.
  showDictSourceSelector: false,
  sectionSlug: null,

  init() {
    this.loadSettings();
    this.userScript = this.$root.dataset.script || 'devanagari';
    this.data = JSON.parse(document.getElementById('payload').textContent);
    this.sectionSlug = this.data.section_slug;

    history.replaceState({ sectionSlug: this.sectionSlug }, '', window.location.href);
    window.addEventListener('popstate', (e) => this.onPopState(e));
    this.$nextTick(() => this.insertSoftHyphensInDOM());
  },

  /** Load user settings from local storage. */
  loadSettings() {
    const settingsStr = localStorage.getItem(READER_CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.fontSize = settings.fontSize || this.fontSize;
        this.textWidth = settings.textWidth || this.textWidth;
        this.dictSources = settings.dictSources || this.dictSources;
        this.sidebarWidth = settings.sidebarWidth || this.sidebarWidth;
      } catch (error) {
        // Old settings are invalid -- rewrite with valid values.
        this.saveSettings();
      }
    }
  },

  /** Save user settings to local storage. */
  saveSettings() {
    const settings = {
      fontSize: this.fontSize,
      textWidth: this.textWidth,
      dictSources: this.dictSources,
      sidebarWidth: this.sidebarWidth,
    };
    localStorage.setItem(READER_CONFIG_KEY, JSON.stringify(settings));
  },

  async changeScript(newScript) {
    await fetch(`/script/${newScript}`);
    this.userScript = newScript;

    this.dictionaryResponse = null;
    this.wordAnalysis = { form: null, lemma: null, parse: null };
    this.analyzeData = { blockSlug: null, words: [], error: null };

    const resp = await fetch(`/api${location.pathname}`);
    if (!resp.ok) return;
    this.data = await resp.json();
    this.$nextTick(() => this.insertSoftHyphensInDOM());
  },

  insertSoftHyphensInDOM() {
    function insertSoftHyphens(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent;
        const aksharas = toAksharas(text);
        const htmlString = aksharas.join('&shy;');

        const temp = document.createElement('span');
        temp.innerHTML = htmlString;

        const fragment = document.createDocumentFragment();
        while (temp.firstChild) {
          fragment.appendChild(temp.firstChild);
        }
        node.parentNode.replaceChild(fragment, node);
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        Array.from(node.childNodes).forEach((child) => insertSoftHyphens(child));
      }
    }

    document.querySelectorAll('s-p').forEach((el) => {
      insertSoftHyphens(el);
    });
  },

  async navigateToSection(url, pushState) {
    try {
      const resp = await fetch(`/api${url}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const newData = await resp.json();

      this.data = newData;
      this.sectionSlug = newData.section_slug;

      if (pushState) {
        history.pushState({ sectionSlug: this.sectionSlug }, '', url);
      }

      const title = newData.section_title
        ? `${newData.text_title} ${newData.section_title} | Ambuda`
        : `${newData.text_title} | Ambuda`;
      document.title = title;

      const textPanel = document.querySelector('article > div');
      if (textPanel) textPanel.scrollTop = 0;

      this.$nextTick(() => this.insertSoftHyphensInDOM());
    } catch {
      window.location.href = url;
    }
  },

  goToPrev() {
    if (this.data.prev_url) {
      this.navigateToSection(this.data.prev_url, true);
    }
  },

  goToNext() {
    if (this.data.next_url) {
      this.navigateToSection(this.data.next_url, true);
    }
  },

  navigateToTocEntry(url) {
    this.navigateToSection(url, true);
  },

  onPopState(event) {
    const slug = event.state && event.state.sectionSlug;
    if (slug && slug !== this.sectionSlug) {
      this.navigateToSection(location.pathname, false);
    }
  },

  /** Query the dictionary and populate the sidebar. */
  async searchDictionary() {
    if (!this.dictQuery || this.dictSources.length === 0) {
      return;
    }
    const baseUrl = Routes.ajaxDictionaryQuery(this.dictSources, this.dictQuery);
    const url = `${baseUrl}?script=${this.userScript}`;
    const resp = await fetch(url);
    if (resp.ok) {
      this.dictionaryResponse = await resp.text();
    } else {
      this.dictionaryResponse = '<p>Sorry, this content is not available right now.</p>';
    }
  },

  async fetchBlockParse(blockSlug) {
    const textSlug = Routes.getTextSlug();
    const url = Routes.parseData(textSlug, blockSlug);

    let resp;
    try {
      resp = await fetch(url);
    } catch (e) {
      return [null, false];
    }

    if (resp.ok) {
      const html = await resp.text();
      return [html, true];
    }
    return ['<p>Sorry, this content is not available right now. (Server error)</p>', false];
  },

  // Click handlers
  // ==============

  /** Generic click handler for multiple objects in the reader. */
  async onClick(e) {
    const $word = e.target.closest('s-w');
    if ($word) {
      this.onClickWord($word);
      return;
    }

    if (e.target.closest('button') || e.target.closest('a')) {
      return;
    }

    const $block = e.target.closest('s-block');
    if ($block) {
      this.onClickBlock($block.dataset.slug);
    }
  },

  async onClickBlock(blockSlug) {
    const block = this.data.blocks.find((b) => b.slug === blockSlug);

    if (block._analyzeWords) {
      this.analyzeData = { blockSlug, words: block._analyzeWords, error: null };
      this.sidebarTab = 'analyze';
      this.showSidebar = true;
      return;
    }

    const [html, ok] = await this.fetchBlockParse(blockSlug);
    if (ok) {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const words = [];
      doc.querySelectorAll('s-w').forEach((el) => {
        words.push({
          form: el.textContent,
          lemma: el.getAttribute('lemma'),
          parse: el.getAttribute('parse'),
        });
      });
      block._analyzeWords = words;
      this.analyzeData = { blockSlug, words, error: null };
    } else {
      this.analyzeData = { blockSlug: null, words: [], error: html };
    }
    this.sidebarTab = 'analyze';
    this.showSidebar = true;
  },

  lookupAnalyzeWord(word) {
    this.dictQuery = word.lemma;
    this.wordAnalysis = { form: word.form, lemma: word.lemma, parse: word.parse };
    this.searchDictionary();
    this.sidebarTab = 'lookup';
  },

  async onClickWord($word) {
    const form = $word.textContent;
    const lemma = $word.getAttribute('lemma');
    const parse = $word.getAttribute('parse');

    this.dictQuery = lemma;
    await this.searchDictionary();

    this.wordAnalysis = { form, lemma, parse };
    this.sidebarTab = 'lookup';
    this.showSidebar = true;
  },

  // Dropdown handlers
  // =================

  /** Toggle the source selection widget's visibility. */
  toggleSourceSelector() {
    this.showDictSourceSelector = !this.showDictSourceSelector;
  },

  /** Close the source selection widget and re-run the query as needed. */
  onClickOutsideOfSourceSelector() {
    // NOTE: With our current bindings, this method will run *every* time we
    // click outside of the selector even if the selector is not open. If the
    // selector is not visible, this method is best left as a no-op.
    if (this.showDictSourceSelector) {
      this.saveSettings();
      this.searchDictionary();
      this.showDictSourceSelector = false;
    }
  },

  startResizeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const DEFAULT_W = 512;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    const onMouseMove = (e) => {
      const w = window.innerWidth - e.clientX;
      const maxW = Math.floor(window.innerWidth * 0.75);
      const halfW = Math.floor(window.innerWidth * 0.5);
      let snapped = w;
      if (Math.abs(w - DEFAULT_W) < 20) snapped = DEFAULT_W;
      else if (Math.abs(w - halfW) < 20) snapped = halfW;
      this.sidebarWidth = Math.max(280, Math.min(maxW, snapped));
      sidebar.style.width = `${this.sidebarWidth}px`;
    };

    const onMouseUp = () => {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      this.saveSettings();
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  },

  // Bookmark handlers
  // =================

  /** Toggle a bookmark on a text block. */
  async toggleBookmark(blockSlug, event) {
    event.preventDefault();
    event.stopPropagation();

    try {
      const resp = await fetch('/api/bookmarks/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ block_slug: blockSlug }),
      });

      if (resp.ok) {
        const data = await resp.json();
        console.log(data.bookmarked ? 'Bookmarked' : 'Bookmark removed');
      } else {
        const error = await resp.json();
        if (resp.status === 401) {
          alert('Please log in to bookmark verses');
        } else {
          alert(`Failed to toggle bookmark: ${error.error || 'Unknown error'}`);
        }
      }
    } catch (error) {
      console.error('Error toggling bookmark:', error);
      alert('Failed to toggle bookmark');
    }
  },
});
