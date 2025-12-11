# Dockerfile Optimization Summary

## Overview

Comprehensive Dockerfile optimization following Docker best practices, focusing on layer caching efficiency, reproducible builds, and CI/CD compatibility.

## Changes Implemented

### 1. Fixed `.gitmodules` for CI/CD Compatibility

**Problem**: Submodules used SSH URLs (`git@github.com:...`) which fail in GitHub Actions without SSH keys.

**Solution**: Changed to HTTPS URLs (`https://github.com/...`)

```diff
- url = git@github.com:BorjaEst/ndx-pose.git
+ url = https://github.com/BorjaEst/ndx-pose.git
```

**Impact**: GitHub Actions can now clone submodules during checkout with `submodules: recursive`.

---

### 2. Reordered Layers for Optimal Caching

**Problem**: Layer ordering didn't follow "least → most frequently changing" principle.

**Old Order**:

1. pyproject.toml (changes occasionally)
2. nwb-extensions (changes rarely)
3. Install dependencies
4. src/ code (changes frequently)

**New Order**:

1. nwb-extensions (changes **least** frequently - external repos)
2. pyproject.toml (changes occasionally - dependency updates)
3. Install dependencies (cached when above unchanged)
4. src/ code (changes **most** frequently - development)

**Impact**:

- Editing `src/` code: Only rebuilds Step 4-5 (~30 seconds)
- Editing `pyproject.toml`: Rebuilds Steps 2-5 (~10+ minutes)
- Editing submodules: Full rebuild (rare occurrence)

---

### 3. Dynamic Version Extraction

**Problem**: Hardcoded version (`__version__ = "0.0.10"`) causes drift from `pyproject.toml`.

**Old Approach**:

```dockerfile
echo '__version__ = "0.0.10"' > src/w2t_bkin/__init__.py
```

**New Approach**:

```dockerfile
PACKAGE_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "__version__ = \"$PACKAGE_VERSION\"" > src/w2t_bkin/__init__.py
```

**Impact**:

- Single source of truth (pyproject.toml)
- No manual version updates needed
- Follows DRY principle

---

### 4. Submodule Verification

**Problem**: Docker build fails cryptically if submodules aren't initialized.

**Solution**: Added explicit verification step that fails fast with clear error message:

```dockerfile
RUN test -f ./nwb-extensions/ndx-events/pyproject.toml || \
    (echo "ERROR: ndx-events submodule incomplete..." && exit 1)
```

**Impact**:

- Clear error messages for missing submodules
- Fails immediately instead of during dependency installation
- Guides developers to run `git submodule update --init --recursive`

---

### 5. Post-Installation Version Verification

**Problem**: No validation that installed version matches expected version.

**Solution**: Added verification step after installation:

```dockerfile
RUN EXPECTED_VERSION=$(grep '^version = ' pyproject.toml | ...) && \
    INSTALLED_VERSION=$(python -c "from w2t_bkin import __version__; print(__version__)") && \
    if [ "$INSTALLED_VERSION" != "$EXPECTED_VERSION" ]; then \
        echo "ERROR: Version mismatch detected!" && exit 1; \
    fi
```

**Impact**:

- Catches version inconsistencies immediately
- Prevents deploying images with wrong versions
- Provides clear diagnostic information

---

### 6. Enhanced Documentation

**Added**:

- Comprehensive layer ordering rationale
- Cache behavior explanations
- Architecture-specific build notes
- Expected rebuild times for different change scenarios

**Impact**: Developers understand why layers are ordered this way and can maintain optimization strategy.

---

## Cache Behavior Reference

| Change Type           | Layers Rebuilt | Rebuild Time   | Frequency                   |
| --------------------- | -------------- | -------------- | --------------------------- |
| Edit `src/*.py` files | Steps 4-5 only | ~30 seconds    | Daily (development)         |
| Edit `pyproject.toml` | Steps 2-5      | ~10-15 minutes | Weekly (dependency updates) |
| Edit submodules       | Full rebuild   | ~15-20 minutes | Monthly (external updates)  |
| Edit base system deps | Full rebuild   | ~15-20 minutes | Quarterly (system updates)  |

---

## Best Practices Applied

✅ **Layer Ordering**: Least → most frequently changing
✅ **Dynamic Values**: No hardcoded versions or configuration
✅ **Fail Fast**: Early validation with clear error messages
✅ **Single Source of Truth**: Version in `pyproject.toml` only
✅ **Comprehensive Documentation**: Explain "why" not just "what"
✅ **CI/CD Compatibility**: HTTPS URLs for submodules
✅ **Image Size Optimization**: Cleanup build artifacts, test files
✅ **Verification**: Post-install validation of expectations
✅ **Cross-Platform**: Architecture-specific compiler flags
✅ **Security**: Non-root user, minimal base image

---

## Migration Notes

### For Local Development

No changes required. The Dockerfile remains compatible with local builds:

```bash
git submodule update --init --recursive
docker build --target worker -t w2t-bkin:worker .
```

### For CI/CD

The `.gitmodules` change enables automatic submodule checkout:

```yaml
- name: Checkout repository
  uses: actions/checkout@v4
  with:
    submodules: recursive # Now works with HTTPS URLs
```

### For Developers Using SSH

You can still use SSH URLs locally by running:

```bash
git config submodule.nwb-extensions/ndx-pose.url git@github.com:BorjaEst/ndx-pose.git
git config submodule.nwb-extensions/ndx-structured-behavior.url git@github.com:BorjaEst/ndx-structured-behavior.git
git config submodule.nwb-extensions/ndx-events.url git@github.com:BorjaEst/ndx-events.git
```

This overrides `.gitmodules` locally without affecting the repository.

---

## Validation Checklist

- [ ] Local build succeeds: `docker build --target worker .`
- [ ] GitHub Actions build succeeds (submodules clone via HTTPS)
- [ ] Version in image matches `pyproject.toml`
- [ ] Editing `src/` code triggers fast rebuild (~30 sec)
- [ ] Editing `pyproject.toml` triggers full dependency install (~10 min)
- [ ] All three NWB extensions install correctly
- [ ] Image size remains under 2GB threshold
- [ ] Container starts without errors

---

## Future Considerations

1. **Build Arguments**: Add `--build-arg BUILD_DATE` to force cache invalidation when needed
2. **Layer Squashing**: Consider squashing final image to reduce size further
3. **Multi-stage Optimization**: Evaluate separating build stage from runtime stage
4. **Registry Caching**: Use `cache-from` and `cache-to` in CI for faster builds
5. **Dependabot**: Set up automated dependency updates for `pyproject.toml`

---

## References

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Dockerfile Layer Caching](https://docs.docker.com/build/cache/)
- [GitHub Actions Checkout](https://github.com/actions/checkout)
- [Containerization Best Practices](vscode-userdata:/c%3A/Users/Borja/AppData/Roaming/Code/User/prompts/containerization-docker-best-practices.instructions.md)
