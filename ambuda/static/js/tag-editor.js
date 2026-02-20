/* Tag editor Alpine components for proofing project tag management. */

// Shared cache for all tag editor instances.
let _allTagsPromise = null;

function fetchAllTags() {
  if (!_allTagsPromise) {
    _allTagsPromise = fetch('/api/proofing/tags')
      .then((r) => r.json())
      .then((data) => data.tags.map((t) => t.name));
  }
  return _allTagsPromise;
}

function invalidateAllTags() {
  _allTagsPromise = null;
}

function TagEditor() {
  return {
    projectSlug: '',
    projectTags: [],
    allTags: [],
    isOpen: false,
    newTag: '',

    init() {
      this.projectSlug = this.$el.dataset.projectSlug || '';
      try {
        this.projectTags = JSON.parse(this.$el.dataset.tags || '[]');
      } catch (e) {
        this.projectTags = [];
      }
      fetchAllTags().then((tags) => { this.allTags = tags; });
    },

    get filteredTags() {
      const q = this.newTag.toLowerCase().trim();
      if (!q) return this.allTags;
      return this.allTags.filter((t) => t.toLowerCase().includes(q));
    },

    get showCreate() {
      const q = this.newTag.trim();
      if (!q) return false;
      return !this.allTags.some((t) => t.toLowerCase() === q.toLowerCase());
    },

    hasTag(name) {
      return this.projectTags.includes(name);
    },

    toggle(name) {
      if (this.hasTag(name)) {
        this.projectTags = this.projectTags.filter((t) => t !== name);
      } else {
        this.projectTags.push(name);
      }
      this.save();
    },

    createTag() {
      const name = this.newTag.trim();
      if (!name) return;
      if (!this.allTags.includes(name)) {
        this.allTags.push(name);
        invalidateAllTags();
      }
      if (!this.hasTag(name)) {
        this.projectTags.push(name);
      }
      this.newTag = '';
      this.save();
    },

    save() {
      fetch(`/api/proofing/projects/${this.projectSlug}/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: this.projectTags }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.ok) {
            this.projectTags = data.tags.map((t) => t.name);
          }
        });
    },

    closeDropdown() {
      this.isOpen = false;
      this.newTag = '';
    },
  };
}

function ProjectList() {
  return {
    selected: new Set(),
    batchOpen: false,
    batchNewTag: '',
    allTags: [],
    batchApplying: false,

    init() {
      fetchAllTags().then((tags) => { this.allTags = tags; });
    },

    get hasSelection() {
      return this.selected.size > 0;
    },

    get selectedCount() {
      return this.selected.size;
    },

    toggleSelect(slug) {
      if (this.selected.has(slug)) {
        this.selected.delete(slug);
      } else {
        this.selected.add(slug);
      }
      // Force Alpine reactivity
      this.selected = new Set(this.selected);
    },

    isSelected(slug) {
      return this.selected.has(slug);
    },

    get batchFilteredTags() {
      const q = this.batchNewTag.toLowerCase().trim();
      if (!q) return this.allTags;
      return this.allTags.filter((t) => t.toLowerCase().includes(q));
    },

    get batchShowCreate() {
      const q = this.batchNewTag.trim();
      if (!q) return false;
      return !this.allTags.some((t) => t.toLowerCase() === q.toLowerCase());
    },

    async batchToggle(tagName) {
      this.batchApplying = true;
      const promises = [];
      for (const slug of this.selected) {
        // Find the tag editor component for this project and update it
        const el = document.querySelector(`[data-project-slug="${slug}"]`);
        if (!el) continue;
        const editor = Alpine.$data(el);
        if (!editor) continue;
        editor.toggle(tagName);
      }
      this.batchApplying = false;
    },

    async batchCreateTag() {
      const name = this.batchNewTag.trim();
      if (!name) return;
      if (!this.allTags.includes(name)) {
        this.allTags.push(name);
        invalidateAllTags();
      }
      this.batchNewTag = '';
      this.batchApplying = true;
      for (const slug of this.selected) {
        const el = document.querySelector(`[data-project-slug="${slug}"]`);
        if (!el) continue;
        const editor = Alpine.$data(el);
        if (!editor) continue;
        if (!editor.hasTag(name)) {
          editor.projectTags.push(name);
          editor.save();
        }
        // Also update the editor's allTags
        if (!editor.allTags.includes(name)) {
          editor.allTags.push(name);
        }
      }
      this.batchApplying = false;
    },

    closeBatchDropdown() {
      this.batchOpen = false;
      this.batchNewTag = '';
    },
  };
}

export { TagEditor, ProjectList };
