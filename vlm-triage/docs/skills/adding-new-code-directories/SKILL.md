---
name: adding-new-code-directories
description: When adding a new top-level code directory to the repository, ensure it is properly integrated with build, test, and documentation systems by updating configuration files.
---

# Skill: Adding New Code Directories

When adding a new top-level code directory (like `models/`) to the repository, several configuration files and build scripts must be updated to ensure the directory is properly integrated with the project's build, test, and documentation systems.

## Overview

This guide covers all the configuration items that need updates when introducing a new code directory.

## Files to Update

### 1. **pyproject.toml** - Build, Test, and Execution Configuration

Multiple locations in `pyproject.toml` reference code directories:

#### 1.1 `make-py-exec` Task
**Location**: `[tool.pixi.tasks]`  
**Current**: `find apps/ lib/ models/ tests/ -name '*.py' | ...`  
**Action**: Add the new directory to the find command  
**Example**: If adding `agents/`:
```toml
make-py-exec = "find apps/ lib/ models/ agents/ tests/ -name '*.py' | xargs grep -l '#!/usr/bin/env -S pixi run' | xargs chmod a+x"
```

#### 1.2 `etest` Task (Extended Test Task)
**Location**: `[tool.pixi.feature.test.tasks.etest]`  
**Current**: `find apps/ lib/ models/ tests/ -name '*.py' | xargs grep -El ...`  
**Action**: Add the new directory to the find command  
**Why**: Ensures all test files with the correct shebang are run in the appropriate environment

#### 1.3 `pytest` Configuration - `testpaths`
**Location**: `[tool.pytest.ini_options]`  
**Current**: `testpaths = ["apps", "lib", "models", "tests"]`  
**Action**: Add the new directory  
**Example**: If adding `agents/`:
```toml
testpaths = ["apps", "lib", "models", "agents", "tests"]
```
**Why**: pytest uses this to know where to discover test files

#### 1.4 `coverage` Configuration - `source`
**Location**: `[tool.coverage.run]`  
**Current**: `source = ["apps", "models", "lib"]`  
**Action**: Add the new directory  
**Example**:
```toml
source = ["apps", "models", "lib", "agents"]
```
**Why**: Ensures coverage reports include code from the new directory

### 2. **mkdocs.yml** - Documentation Configuration

#### 2.1 `watch` Setting
**Location**: Top-level `watch:` key  
**Current**: `watch: ["apps", "lib", "models", "scripts", "tests"]`  
**Action**: Add the new directory  
**Example**: If adding `agents/`:
```yaml
watch: ["apps", "lib", "models", "scripts", "tests", "agents"]
```
**Why**: Enables hot-reload of documentation when files in the new directory change

### 3. **.gitignore** - Git Exclusions (if applicable)

**Location**: Repository root `.gitignore`  
**Check if needed**: Only if the new directory has generated files or artifacts  
**Example**: If `models/` has cached model weights:
```
models/**/*.pth
models/**/*.bin
```

### 4. **conftest.py** - Test Configuration (if applicable)

**Location**: Repository root `conftest.py`  
**Check if needed**: Only if the new directory has special test setup requirements  
**Example**: If adding `agents/` with async tests:
```python
# Add to existing conftest imports
import asyncio

# May need to configure pytest-asyncio or other fixtures
```

### 5. **scripts/gen_ref_pages.py** - Auto-generated Documentation (if applicable)

**Location**: `scripts/gen_ref_pages.py`  
**Check if needed**: Only if you want auto-generated API documentation  
**Action**: Add the new module to the documentation generation script  
**Why**: Automatically generates API reference pages from docstrings

### 6. **Ruff Configuration** - Linting and Formatting

**Location**: `pyproject.toml` - `[tool.ruff]` sections  
**Check if needed**: Usually not needed, as Ruff discovers Python files automatically  
**But verify**: Check if there are `include` or `exclude` patterns that need updating:
```toml
[tool.ruff]
include = ["apps/**/*.py", "lib/**/*.py", "models/**/*.py", ...]
exclude = ["venv", ".venv", "dist", "build"]
```

## Checklist

When adding a new directory, follow this checklist:

- [ ] **pyproject.toml** - Update `make-py-exec` task
- [ ] **pyproject.toml** - Update `etest` task
- [ ] **pyproject.toml** - Update `testpaths` in pytest config
- [ ] **pyproject.toml** - Update `source` in coverage config
- [ ] **mkdocs.yml** - Update `watch` list
- [ ] **.gitignore** - Add patterns if needed (e.g., generated artifacts)
- [ ] **conftest.py** - Add fixtures/configuration if needed
- [ ] **scripts/gen_ref_pages.py** - Add module if auto-documentation is desired
- [ ] **Ruff config** - Verify `include`/`exclude` patterns if custom
- [ ] **README.md** - Update directory structure section (optional but recommended)

## Verification Steps

After updating the configuration:

### 1. Verify Test Discovery
```bash
pixi run etest --collect-only | grep "test session starts" -A 5
```

### 2. Verify File Permissions
```bash
pixi run make-exec
# Then check that files with shebang are executable
ls -l <new_directory>/*.py | grep -E "\-rwxr"
```

### 3. Verify Coverage
```bash
pixi run cov
# Check that coverage report includes the new directory
cat .coverage | grep <new_directory>
```

### 4. Verify Documentation
```bash
pixi run mkdocs build
# Check that documentation includes pages from the new directory
ls data/vlm-triage-docs/reference/ | grep <new_directory>
```

### 5. Test Lint and Format
```bash
pixi run format
pixi run lint-ruff
```

## Common Examples

### Example 1: Adding `agents/` Directory

**Changes needed**:

```toml
# pyproject.toml - [tool.pixi.tasks]
make-py-exec = "find apps/ lib/ models/ agents/ tests/ -name '*.py' | ..."

# pyproject.toml - [tool.pixi.feature.test.tasks.etest]
cmd = "find apps/ lib/ models/ agents/ tests/ -name '*.py' | ..."

# pyproject.toml - [tool.pytest.ini_options]
testpaths = ["apps", "lib", "models", "agents", "tests"]

# pyproject.toml - [tool.coverage.run]
source = ["apps", "models", "lib", "agents"]
```

```yaml
# mkdocs.yml
watch: ["apps", "lib", "models", "scripts", "tests", "agents"]
```

### Example 2: Adding `third-party/custom_models/` Subdirectory

**Changes needed** (same as above, replacing `agents/` with `third-party/custom_models/`)

**Additional**: If this is a subdirectory, verify the path with slashes:
```toml
testpaths = ["apps", "lib", "models", "tests", "third-party/custom_models"]
```

## Troubleshooting

### Tests not being discovered
- **Cause**: `testpaths` not updated in `pyproject.toml`
- **Fix**: Add the directory to `[tool.pytest.ini_options] testpaths`
- **Verify**: `pixi run etest --collect-only`

### Files not made executable
- **Cause**: `make-py-exec` task not updated
- **Fix**: Add the directory to the find command in `[tool.pixi.tasks] make-py-exec`
- **Verify**: `pixi run make-exec && ls -la <new_directory>/*.py | head -5`

### Coverage not including new directory
- **Cause**: `source` list in coverage config not updated
- **Fix**: Add the directory to `[tool.coverage.run] source`
- **Verify**: `pixi run cov && cat .coverage`

### Documentation not building
- **Cause**: `watch` list in mkdocs.yml not updated (or gen_ref_pages.py if auto-docs)
- **Fix**: Update `watch:` in `mkdocs.yml` and/or update `scripts/gen_ref_pages.py`
- **Verify**: `pixi run mkdocs build`

## Related Skills

- **start-development** - Starting new feature development
- **codebase-navigation-tooling** - Understanding codebase structure

## See Also

- `pyproject.toml` - Full project configuration
- `mkdocs.yml` - Documentation build configuration
- `.gitignore` - Git exclusion patterns
- `CONTRIBUTING.md` - Contribution guidelines
