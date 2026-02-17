# Feature Request: Enhanced Word Sidebar for Sanskrit Learning

## Problem Statement

When Sanskrit learners click on a word in the reader, they currently see only the dictionary meaning. This is insufficient for actually learning from the text. Learners need much richer context to understand:

- How compound words are formed (sandhi and samāsa)
- The grammatical structure of words at varying depth levels
- How words function in their specific verse context
- The natural prose order of poetic verses (anvaya)

Without these pedagogical aids, learners cannot effectively use Ambuda as a learning tool—they can only passively read with external references.

## User Stories

**As a beginning Sanskrit student**, I want to see word splits and basic grammatical information so that I can understand the structure of words I encounter.

**As an intermediate learner**, I want to explore compound analysis, etymology, and intermediate grammar so that I can deepen my understanding of Sanskrit morphology.

**As an advanced student**, I want access to Pāṇinian sūtra references and detailed technical analysis so that I can study traditional grammatical methodology.

**As any Sanskrit reader**, I want to see verses rearranged in prose order (anvaya) with syntactic roles highlighted so that I can understand complex poetic constructions.

## Proposed Solution

Replace the current meanings-only sidebar with a comprehensive word exploration panel containing:

### 1. Pada Vibhāga (Word Splitting)
- Visual breakdown of compound/sandhi splits
- Identification of compound types (tatpuruṣa, karmadhāraya, dvandva, bahuvrīhi)
- Vigraha-vākya (expanded paraphrases)
- Step-by-step sandhi transformations with rule names

### 2. Enhanced Meaning Section
- **Primary gloss**: Short default meaning
- **Dictionary reference**: Monier-Williams or Apte entry
- **Contextual meaning**: Highlighted explanation of how the word functions in this specific verse

### 3. Progressive Grammar Levels
Display grammar in three collapsible tabs matching learner proficiency:

**Basic**: Essential information (लिङ्ग, वचन, विभक्ति / पुरुष, लकार)
- Presented in simple two-column key-value layout
- Suitable for beginners

**Intermediate**: Deeper analysis (प्रकृति, प्रत्यय, समासविग्रह, उपसर्ग, कृदन्त, व्युत्पत्ति)
- Same clean layout format
- For students comfortable with morphology

**Advanced**: Scholarly detail (अष्टाध्यायी सूत्र references)
- Cards showing sūtra number, Sanskrit text, and English explanation
- For serious students of Pāṇinian grammar

### 4. Anvaya View
A separate tab in the main reading area that:
- Rearranges verse words in prose order (कर्ता → कर्म → क्रिया)
- Color-codes syntactic roles: subject (blue), object (red), verb (purple), adjectives (amber)
- Provides toggle for showing/hiding English gloss

## User Experience Requirements

1. **Defaults should favor learners**: All sections visible by default, with collapsibility for advanced users who want less clutter
2. **Progressive disclosure**: Information organized by complexity level
3. **Visual clarity**: Use color, spacing, and typography to make information scannable
4. **Contextual help**: Each section should have brief explanations of unfamiliar terminology
5. **Mobile responsive**: Works on tablets and phones where learners often study

## Success Criteria

- Users can explore words without leaving the reading flow
- Beginning students can access grammar information at their level
- Advanced students can dive deep into technical analysis
- Learners can toggle between verse form and prose order
- The interface remains fast and responsive

## Technical Considerations (for implementer)

- Solution should integrate with existing reader architecture
- Needs backend data structure extensions for full feature set
- Some features can start with example/placeholder data until backend support is added
- Should work with existing parse data format where possible

## Benefits

1. **Learning efficiency**: Students spend less time switching between tools
2. **Pedagogical value**: Progressive disclosure matches how Sanskrit is taught
3. **Retention**: Contextual meaning helps students remember words
4. **Accessibility**: Makes advanced grammatical analysis available to all users
5. **Differentiation**: Sets Ambuda apart as a true learning platform, not just a text repository

## Related Work

Similar progressive disclosure patterns are used in:
- Language learning apps (Duolingo's grammar tips)
- Quranic study tools (word-by-word analysis)
- Classical language platforms (Perseus Digital Library)

## Priority

**High** - This directly addresses Ambuda's mission to make Sanskrit accessible. The current dictionary-only approach is a significant barrier to learning.

---

**Labels**: enhancement, pedagogy, reader, learner-experience
**Milestone**: Reader improvements
**Area**: Frontend, Backend (data modeling)
