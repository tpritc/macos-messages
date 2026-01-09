---
description: Release a new version of macos-messages to PyPI
argument-hint: <version>
---

# Release macos-messages version $ARGUMENTS

Follow these steps to release version $ARGUMENTS:

## 1. Update version numbers

Update the version in both files:
- `pyproject.toml`: `version = "$ARGUMENTS"`
- `src/messages/__init__.py`: `__version__ = "$ARGUMENTS"`

## 2. Update CHANGELOG.md

Add a new section at the top (below the header) with today's date:

```markdown
## [$ARGUMENTS] - YYYY-MM-DD

### Added
- (new features, if any)

### Changed
- (changes to existing functionality, if any)

### Fixed
- (bug fixes, if any)
```

Add the release link at the bottom of the file:
```markdown
[$ARGUMENTS]: https://github.com/tpritc/macos-messages/releases/tag/v$ARGUMENTS
```

## 3. Run tests

Ensure all tests pass before proceeding:
```bash
uv run pytest
```

## 4. Commit the version bump

Commit all version and changelog changes.

## 5. Create and push the tag

```bash
git tag -a v$ARGUMENTS -m "Release $ARGUMENTS"
git push origin v$ARGUMENTS
```

## 6. Create GitHub release

Use the changelog content for the release notes, including the section headings (### Added, ### Changed, ### Fixed) for consistency:

```bash
gh release create v$ARGUMENTS --title "$ARGUMENTS" --notes "### Changed

- First change
- Second change"
```

## 7. Build and publish to PyPI

```bash
uv build
uv publish --token "$(op read 'op://Private/PyPI/api token' --account my.1password.com)"
```

## 8. Verify

- Check https://pypi.org/project/macos-messages/ shows the new version
- Check https://github.com/tpritc/macos-messages/releases shows the release
