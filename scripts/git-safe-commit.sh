#!/usr/bin/env bash
#
# git safe-commit — Production-grade commit safety pipeline (Python)
#
# Enforces: lint -> format -> typecheck -> test -> security -> stage -> commit
#
# Usage:
#   git safe-commit              # run full pipeline and commit
#   git safe-commit -m "msg"     # run full pipeline and commit with message
#   git safe-commit --check      # run pipeline only (no commit)
#
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'

STEP=0; FAILED=0; COMMIT_MSG=""

info()  { echo -e "${CYAN}i${NC}  $*"; }
ok()    { echo -e "${GREEN}v${NC}  $*"; }
warn()  { echo -e "${YELLOW}w${NC}  $*"; }
fail()  { echo -e "${RED}x${NC}  $*"; FAILED=$((FAILED + 1)); }
header() { STEP=$((STEP + 1)); echo ""; echo -e "${BOLD}[Step ${STEP}]${NC} $*"; }

run_check() {
  local name="$1"; shift
  if "$@" 2>&1; then
    ok "${name}"
  else
    fail "${name} -- see output above"
    return 1
  fi
}

# Parse args
DO_COMMIT=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) DO_COMMIT=false; shift ;;
    -m) COMMIT_MSG="$2"; shift 2 ;;
    -m*) COMMIT_MSG="${1#-m}"; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Safe single-quote helper for grep patterns (avoids bash single-quote escaping issues)
SQ="'"

# Step 1: Git state check
header "Git State Check"
if ! git status --porcelain > /dev/null 2>&1; then
  fail "Git repository not found or corrupted"; exit 1
fi
if grep -rn '<<<<<<<' --include='*.py' --include='*.html' --include='*.md' --include='*.yml' --include='*.yaml' --include='*.json' . 2>/dev/null | grep -v '.git/' | head -5; then
  fail "Merge conflict markers detected! Resolve conflicts first."
fi
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
[ "$BRANCH" = "HEAD" ] && warn "Detached HEAD state"
ok "Git state is stable (branch: ${BRANCH})"

# Step 2: Lint (flake8/ruff)
header "Linting"
if command -v flake8 &>/dev/null; then
  run_check "flake8" flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=.git,__pycache__,venv,.venv || true
elif command -v ruff &>/dev/null; then
  run_check "ruff" ruff check . || true
else
  warn "No linter (flake8/ruff) found -- install with: pip install flake8"
fi

# Step 3: Format check (black)
header "Format Check"
if command -v black &>/dev/null; then
  run_check "black" black --check . --exclude="venv|.venv|__pycache__" 2>/dev/null || {
    warn "Formatting issues found -- run 'black .' to fix"
  }
else
  warn "black not installed -- skipping format check"
fi

# Step 4: Type check (mypy)
header "Type Check"
if command -v mypy &>/dev/null; then
  run_check "mypy" mypy . --ignore-missing-imports 2>/dev/null || true
else
  warn "mypy not installed -- skipping type check"
fi

# Step 5: Tests
header "Tests"
if [ -f "pytest.ini" ] || [ -f "pyproject.toml" ] || ls tests/ &>/dev/null; then
  run_check "pytest" python -m pytest . -v --tb=short 2>/dev/null || true
else
  warn "No pytest config found -- skipping tests"
fi

# Step 6: Security scan
header "Security Scan"
if command -v bandit &>/dev/null; then
  run_check "bandit" bandit -r . -x venv,__pycache__ -l 2>/dev/null || true
else
  warn "bandit not installed -- skipping security scan"
fi
# Check for hardcoded secrets (use helper SQ var for safe single-quote embedding)
SECRET_PATTERNS="(api[_-]?key|secret|token|password|credential)[\"\s:=]+[\"${SQ}][A-Za-z0-9_\-]{20,}[\"${SQ}]"
if grep -rn -i -E "$SECRET_PATTERNS" --include='*.py' . 2>/dev/null | grep -v '.git/' | grep -v '.env'; then
  warn "Possible hardcoded secrets detected -- review flagged lines above"
else
  ok "No obvious secrets detected"
fi
# Check for .env in staging
if git diff --cached --name-only | grep -q '\.env$'; then
  fail ".env file is staged! This should NEVER be committed."
fi

# Step 7: Staging safety
header "Staging Safety Check"
DANGEROUS_PATTERNS="__pycache__|\.pyc|\.egg|dist|build|\.venv|venv|\.cache|\.pytest_cache|coverage|logs"
STAGED_DANGEROUS=$(git diff --cached --name-only | grep -E "$DANGEROUS_PATTERNS" || true)
if [ -n "$STAGED_DANGEROUS" ]; then
  fail "Dangerous files staged -- removing:"
  echo "$STAGED_DANGEROUS" | while read -r f; do
    echo "  x $f"
    git reset HEAD "$f" 2>/dev/null || true
  done
fi

# Result
echo ""
echo "==========================================="
if [ "$FAILED" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}  v All checks passed!${NC}"
  echo "==========================================="
  if [ "$DO_COMMIT" = true ]; then
    if [ -n "$COMMIT_MSG" ]; then
      git commit -m "$COMMIT_MSG"
      echo -e "${GREEN}${BOLD}  v Commit successful!${NC}"
      echo "To push: git push origin $(git rev-parse --abbrev-ref HEAD)"
    else
      warn "No commit message provided. Files are staged."
      echo "  Run: git commit -m \"message\""
    fi
  else
    ok "Check mode -- no commit made."
  fi
else
  echo -e "${RED}${BOLD}  x ${FAILED} check(s) failed. Commit BLOCKED.${NC}"
  echo "==========================================="
  echo "Fix the errors above and run git safe-commit again."
  exit 1
fi
