# Quick Reference: GitHub Issue Creation

## To Create the GitHub Issue

Copy the content from `FEATURE_ISSUE.md` into a new GitHub issue on the kvchitrapu/ambuda repository.

### Issue Details

- **Title**: Enhanced Word Sidebar for Sanskrit Learning
- **Type**: Feature / Enhancement
- **Labels**: `enhancement`, `pedagogy`, `reader`, `learner-experience`
- **Priority**: High
- **Body**: Contents of FEATURE_ISSUE.md

### GitHub CLI Command (if available)

```bash
gh issue create \
  --title "Enhanced Word Sidebar for Sanskrit Learning" \
  --body-file FEATURE_ISSUE.md \
  --label "enhancement,pedagogy,reader,learner-experience"
```

### Manual Creation Steps

1. Go to https://github.com/kvchitrapu/ambuda/issues/new
2. Set title: "Enhanced Word Sidebar for Sanskrit Learning"
3. Copy entire content of `FEATURE_ISSUE.md` into the description
4. Add labels: enhancement, pedagogy, reader, learner-experience
5. Submit

### Implementation Reference

The feature has already been implemented on branch `copilot/enhanced-word-sidebar-feature`.
See `IMPLEMENTATION_SUMMARY.md` for technical details.

### Key Points for Issue Discussion

- Feature addresses core learning needs for Sanskrit students
- Uses progressive disclosure (3 levels: Basic, Intermediate, Advanced)
- Includes visual word splitting, contextual meanings, and prose order view
- Some components need backend data extensions to be fully functional
- Current implementation uses example data where backend support is pending

### Related Files

- Feature description: `FEATURE_ISSUE.md`
- Implementation details: `IMPLEMENTATION_SUMMARY.md`
- Modified files: See git log on `copilot/enhanced-word-sidebar-feature`

---

**Note**: This is documentation for creating a GitHub issue to describe the feature.
The actual implementation is complete and committed to the branch.
