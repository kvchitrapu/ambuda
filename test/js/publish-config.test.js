import createPublishConfig, { titleToSlug } from '@/publish-config';

function setup(overrides = {}) {
  window.PUBLISH_CONFIG = overrides.config || { publish: [], pages: [] };
  window.PUBLISH_CONFIG_SCHEMA = overrides.schema || {
    properties: {
      title: { type: 'string' },
      slug: { type: 'string' },
      target: { anyOf: [{ type: 'string' }, { type: 'null' }] },
      author: { anyOf: [{ type: 'string' }, { type: 'null' }] },
      genre: { anyOf: [{ type: 'string' }, { type: 'null' }] },
      language: { $ref: '#/$defs/LanguageCode', default: 'sa' },
      parent_slug: { anyOf: [{ type: 'string' }, { type: 'null' }] },
    },
    $defs: {
      LanguageCode: {
        type: 'string',
        enum: ['sa', 'en', 'hi', 'ta'],
      },
    },
    required: ['slug', 'title'],
  };
  window.PROJECT_SLUG = 'test-project';
  window.LANGUAGE_LABELS = { sa: 'Sanskrit', en: 'English', hi: 'Hindi', ta: 'Tamil' };
  window.GENRE_NAMES = overrides.genres || ['काव्य', 'नाटक'];
  window.AUTHOR_NAMES = overrides.authors || ['Vālmīki', 'Kālidāsa'];

  const component = createPublishConfig();
  component.init();
  return component;
}

afterEach(() => {
  delete window.PUBLISH_CONFIG;
  delete window.PUBLISH_CONFIG_SCHEMA;
  delete window.PROJECT_SLUG;
  delete window.LANGUAGE_LABELS;
  delete window.GENRE_NAMES;
  delete window.AUTHOR_NAMES;
});

test('init with empty config', () => {
  const c = setup();
  expect(c.config.publish).toEqual([]);
  expect(c.config.pages).toEqual([]);
  expect(c.fields.length).toBeGreaterThan(0);
});

test('init loads existing entries', () => {
  const c = setup({
    config: { publish: [{ slug: 'test', title: 'Test' }], pages: [] },
  });
  expect(c.config.publish).toHaveLength(1);
  expect(c.config.publish[0].slug).toBe('test');
  expect(c.config.publish[0].expanded).toBe(false);
});

test('generateFieldsFromSchema resolves $ref for language', () => {
  const c = setup();
  const langField = c.fields.find(f => f.name === 'language');
  expect(langField.enum).toEqual(['sa', 'en', 'hi', 'ta']);
  expect(langField.type).toBe('string');
});

test('generateFieldsFromSchema renames target to Filter', () => {
  const c = setup();
  const targetField = c.fields.find(f => f.name === 'target');
  expect(targetField.label).toBe('Filter');
});

test('addPublishEntry adds an expanded entry with defaults', () => {
  const c = setup();
  c.addPublishEntry();
  expect(c.config.publish).toHaveLength(1);
  const entry = c.config.publish[0];
  expect(entry.expanded).toBe(true);
  expect(entry.slug).toBe('');
  expect(entry.title).toBe('');
});

test('removePublishEntry removes empty entry without confirm', () => {
  const c = setup();
  c.addPublishEntry();
  c.removePublishEntry(0);
  expect(c.config.publish).toHaveLength(0);
});

test('removePublishEntry prompts for non-empty entry', () => {
  const c = setup();
  c.addPublishEntry();
  c.config.publish[0].title = 'Something';
  global.confirm = jest.fn(() => false);
  c.removePublishEntry(0);
  expect(c.config.publish).toHaveLength(1);
  global.confirm = jest.fn(() => true);
  c.removePublishEntry(0);
  expect(c.config.publish).toHaveLength(0);
});

test('getConfigLabel returns title (slug) when both set', () => {
  const c = setup();
  expect(c.getConfigLabel({ title: 'Foo', slug: 'foo' })).toBe('Foo (foo)');
});

test('generateJSON excludes empty optional fields', () => {
  const c = setup();
  c.addPublishEntry();
  c.config.publish[0].title = 'T';
  c.config.publish[0].slug = 's';
  const json = JSON.parse(c.generateJSON());
  expect(json.publish[0]).toEqual({ title: 'T', slug: 's' });
});

test('generateJSON includes non-empty optional fields', () => {
  const c = setup();
  c.addPublishEntry();
  Object.assign(c.config.publish[0], { title: 'T', slug: 's', author: 'A' });
  const json = JSON.parse(c.generateJSON());
  expect(json.publish[0].author).toBe('A');
});

test('language picker: filtered returns all when no query', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  const all = c.pickers.lang.filtered(entry);
  expect(all).toHaveLength(4);
});

test('language picker: filtered filters by label', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  entry._lang_query = 'san';
  expect(c.pickers.lang.filtered(entry)).toHaveLength(1);
  expect(c.pickers.lang.filtered(entry)[0].code).toBe('sa');
});

test('language picker: select sets value', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  c.pickers.lang.select(entry, { code: 'ta', label: 'Tamil' });
  expect(entry.language).toBe('ta');
  expect(entry._lang_open).toBe(false);
});

test('language picker: displayValue shows label when idle', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  entry.language = 'en';
  expect(c.pickers.lang.displayValue(entry)).toBe('English');
});

test('genre picker: filtered returns all when no query', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  expect(c.pickers.genre.filtered(entry)).toEqual(['काव्य', 'नाटक']);
});

test('genre picker: filtered filters by substring', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  entry._genre_query = 'काव्य';
  expect(c.pickers.genre.filtered(entry)).toHaveLength(1);
});

test('genre picker: select sets value', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  c.pickers.genre.select(entry, 'काव्य');
  expect(entry.genre).toBe('काव्य');
});

test('addGenre adds to list and sorts', () => {
  const c = setup({ genres: ['B', 'D'] });
  c.newGenreName = 'C';
  c.addGenre();
  expect(c.genres).toEqual(['B', 'C', 'D']);
  expect(c.newGenreOpen).toBe(false);
});

test('addGenre does not add duplicates', () => {
  const c = setup({ genres: ['A'] });
  c.newGenreName = 'A';
  c.addGenre();
  expect(c.genres).toEqual(['A']);
});

test('author picker: filtered returns all when no query', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  expect(c.pickers.author.filtered(entry)).toEqual(['Vālmīki', 'Kālidāsa']);
});

test('author picker: filtered filters by substring', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  entry._author_query = 'vāl';
  expect(c.pickers.author.filtered(entry)).toHaveLength(1);
  expect(c.pickers.author.filtered(entry)[0]).toBe('Vālmīki');
});

test('author picker: select sets value', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  c.pickers.author.select(entry, 'Kālidāsa');
  expect(entry.author).toBe('Kālidāsa');
});

test('addAuthor adds to list and sorts', () => {
  const c = setup({ authors: ['B', 'D'] });
  c.newAuthorName = 'C';
  c.addAuthor();
  expect(c.authors).toEqual(['B', 'C', 'D']);
  expect(c.newAuthorOpen).toBe(false);
});

test('addAuthor does not add duplicates', () => {
  const c = setup({ authors: ['A'] });
  c.newAuthorName = 'A';
  c.addAuthor();
  expect(c.authors).toEqual(['A']);
});

test('getPreviewUrl returns correct url', () => {
  const c = setup();
  expect(c.getPreviewUrl('my-text')).toBe('/proofing/test-project/publish/my-text/preview');
  expect(c.getPreviewUrl('')).toBe('#');
});

test('picker open/close/search lifecycle', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];

  c.pickers.lang.open(entry);
  expect(entry._lang_open).toBe(true);
  expect(entry._lang_query).toBe('');
  expect(entry._lang_sel).toBe(0);

  c.pickers.lang.search(entry, 'hin');
  expect(entry._lang_query).toBe('hin');
  expect(entry._lang_sel).toBe(0);

  c.pickers.lang.close(entry);
  expect(entry._lang_open).toBe(false);
  expect(entry._lang_query).toBeUndefined();
});

test('picker keydown Enter selects item', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  c.pickers.lang.open(entry);

  const event = { key: 'Enter', preventDefault: jest.fn() };
  c.pickers.lang.keydown(entry, event);
  expect(event.preventDefault).toHaveBeenCalled();
  expect(entry.language).toBe('sa');
  expect(entry._lang_open).toBe(false);
});

test('picker keydown Escape closes', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  c.pickers.lang.open(entry);

  const event = { key: 'Escape', preventDefault: jest.fn() };
  c.pickers.lang.keydown(entry, event);
  expect(entry._lang_open).toBe(false);
});

// -- titleToSlug tests --

// Sanscript is a browser global, so we mock it for Devanagari tests
function withSanscript(map, fn) {
  global.Sanscript = { t: (str, from, to) => map[str] || str };
  try { fn(); } finally { delete global.Sanscript; }
}

test('titleToSlug: pure Devanagari title', () => {
  withSanscript({ 'रामायणम्': 'rAmAyaNam' }, () => {
    expect(titleToSlug('रामायणम्')).toBe('ramayanam');
  });
});

test('titleToSlug: handles ś/ṣ → sh', () => {
  withSanscript({ 'विष्णुपुराणम्': 'viSNupurANam' }, () => {
    expect(titleToSlug('विष्णुपुराणम्')).toBe('vishnupuranam');
  });
});

test('titleToSlug: mixed Devanagari with spaces → hyphens', () => {
  withSanscript({ 'राम चरित': 'rAma carita' }, () => {
    expect(titleToSlug('राम चरित')).toBe('rama-carita');
  });
});

test('titleToSlug: already-Latin input passes through', () => {
  expect(titleToSlug('ramayana')).toBe('ramayana');
});

test('titleToSlug: Latin with diacritics normalized', () => {
  expect(titleToSlug('Rāmāyaṇa')).toBe('ramayana');
});

test('titleToSlug: empty string → empty string', () => {
  expect(titleToSlug('')).toBe('');
});

test('titleToSlug: leading/trailing special chars trimmed', () => {
  expect(titleToSlug('--hello--')).toBe('hello');
});

test('titleToSlug: consecutive hyphens collapsed', () => {
  expect(titleToSlug('foo   bar')).toBe('foo-bar');
});

test('titleToSlug: G (ṅ) → n', () => {
  withSanscript({ 'अङ्गम्': 'aGgam' }, () => {
    expect(titleToSlug('अङ्गम्')).toBe('angam');
  });
});

test('titleToSlug: J (ñ) → n', () => {
  withSanscript({ 'पञ्चतन्त्रम्': 'paJcatantram' }, () => {
    expect(titleToSlug('पञ्चतन्त्रम्')).toBe('pancatantram');
  });
});

test('titleToSlug: M → m before labial (p)', () => {
  withSanscript({ 'सम्पदा': 'saMpadA' }, () => {
    expect(titleToSlug('सम्पदा')).toBe('sampada');
  });
});

test('titleToSlug: M → m before labial (b)', () => {
  withSanscript({ 'सम्बन्धः': 'saMbandhaH' }, () => {
    expect(titleToSlug('सम्बन्धः')).toBe('sambandhah');
  });
});

test('titleToSlug: M → m before sibilant (z/ś)', () => {
  withSanscript({ 'संशय': 'saMzaya' }, () => {
    expect(titleToSlug('संशय')).toBe('samshaya');
  });
});

test('titleToSlug: M → m before S (ṣ)', () => {
  withSanscript({ 'संस्कृतम्': 'saMskRtam' }, () => {
    expect(titleToSlug('संस्कृतम्')).toBe('samskrtam');
  });
});

test('titleToSlug: M → n before non-labial/sibilant', () => {
  withSanscript({ 'संगीतम्': 'saMgItam' }, () => {
    expect(titleToSlug('संगीतम्')).toBe('sangitam');
  });
});

test('titleToSlug: M → m before h', () => {
  withSanscript({ 'सिंहः': 'siMhaH' }, () => {
    expect(titleToSlug('सिंहः')).toBe('simhah');
  });
});

// -- isDuplicateSlug tests --

test('isDuplicateSlug: no duplicate returns false', () => {
  const c = setup({
    config: { publish: [{ slug: 'a', title: 'A' }, { slug: 'b', title: 'B' }], pages: [] },
  });
  expect(c.isDuplicateSlug(c.config.publish[0])).toBe(false);
});

test('isDuplicateSlug: same slug on another entry returns true', () => {
  const c = setup({
    config: { publish: [{ slug: 'a', title: 'A' }, { slug: 'a', title: 'B' }], pages: [] },
  });
  expect(c.isDuplicateSlug(c.config.publish[0])).toBe(true);
  expect(c.isDuplicateSlug(c.config.publish[1])).toBe(true);
});

test('isDuplicateSlug: own slug does not flag itself', () => {
  const c = setup({
    config: { publish: [{ slug: 'unique', title: 'Only' }], pages: [] },
  });
  expect(c.isDuplicateSlug(c.config.publish[0])).toBe(false);
});

test('isDuplicateSlug: empty slug is not a duplicate', () => {
  const c = setup({
    config: { publish: [{ slug: '', title: 'A' }, { slug: '', title: 'B' }], pages: [] },
  });
  expect(c.isDuplicateSlug(c.config.publish[0])).toBe(false);
});

// -- Drag-and-drop reorder tests --

function mockDropEvent(index) {
  const el = { dataset: { index: String(index) }, closest: (sel) => (sel === '[data-index]' ? el : null) };
  return { target: el };
}

test('onDrop reorders entries forward', () => {
  const c = setup({
    config: { publish: [{ slug: 'a', title: 'A' }, { slug: 'b', title: 'B' }, { slug: 'c', title: 'C' }], pages: [] },
  });
  c.dragIndex = 0;
  c.onDrop(mockDropEvent(2));
  expect(c.config.publish.map(e => e.slug)).toEqual(['b', 'a', 'c']);
});

test('onDrop reorders entries backward', () => {
  const c = setup({
    config: { publish: [{ slug: 'a', title: 'A' }, { slug: 'b', title: 'B' }, { slug: 'c', title: 'C' }], pages: [] },
  });
  c.dragIndex = 2;
  c.onDrop(mockDropEvent(0));
  expect(c.config.publish.map(e => e.slug)).toEqual(['c', 'a', 'b']);
});

// -- Auto-slug tests --

test('onTitleInput auto-populates slug when not manually edited', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  entry.title = 'Rāmāyaṇa';
  c.onTitleInput(entry);
  expect(entry.slug).toBe('ramayana');
});

test('onTitleInput stops auto-populating after manual slug edit', () => {
  const c = setup();
  c.addPublishEntry();
  const entry = c.config.publish[0];
  entry.title = 'Foo';
  c.onTitleInput(entry);
  expect(entry.slug).toBe('foo');
  c.onSlugInput(entry);
  entry.title = 'Bar';
  c.onTitleInput(entry);
  expect(entry.slug).toBe('foo');
});
