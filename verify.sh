#!/bin/bash
# Verification script for DeepDiver Trading Swarm

echo "🔍 DeepDiver - System Verification"
echo "==================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Check files exist
echo "📁 Checking required files..."
REQUIRED_FILES=(
    "run.py"
    "run.sh"
    ".env.example"

    ".gitignore"
    "README.md"
    "docs/PROJECT_SUMMARY.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (MISSING)"
        ((ERRORS++))
    fi
done

echo ""
echo "📂 Checking directories..."
REQUIRED_DIRS=(
    "app"
    "app/agents"
    "app/dashboard"
    "app/templates"
    "app/data"
    "app/data/history"
    "app/data/routines"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "  ${GREEN}✓${NC} $dir/"
    else
        echo -e "  ${RED}✗${NC} $dir/ (MISSING)"
        ((ERRORS++))
    fi
done

echo ""
echo "🔒 Checking for sensitive data..."

# Check for hardcoded API keys (patterns indicating credentials in code)
echo -e "  Checking for hardcoded credentials..."
CREDENTIAL_PATTERNS=(
    'ALPACA_API_KEY\s*=\s*["\047][A-Z0-9]'
    'ALPACA_SECRET_KEY\s*=\s*["\047][A-Z0-9]'
    'FINNHUB_API_KEY\s*=\s*["\047][a-z0-9]'
    'SUPABASE_KEY\s*=\s*["\047]'
    'OPENROUTER_API_KEY\s*=\s*["\047]'
    'supabase_key\s*=\s*["\047]'
    'api_key\s*=\s*["\047][A-Z0-9]{20,}'
)

FOUND_HARDCODED=false
for pattern in "${CREDENTIAL_PATTERNS[@]}"; do
    if grep -rE "$pattern" app/ 2>/dev/null | grep -v ".git" | grep -v ".pyc" > /dev/null; then
        echo -e "  ${RED}✗${NC} Found hardcoded credential pattern in app/"
        grep -rE "$pattern" app/ 2>/dev/null | grep -v ".git" | grep -v ".pyc" | head -3
        FOUND_HARDCODED=true
        ((ERRORS++))
        break
    fi
done

if [ "$FOUND_HARDCODED" = false ]; then
    echo -e "  ${GREEN}✓${NC} No hardcoded credentials found"
fi

# Check for absolute paths to user directories
echo -e "  Checking for hardcoded file paths..."
if grep -rE "/Users/[a-zA-Z]+/" app/ 2>/dev/null | grep -v ".git" | grep -v ".pyc" > /dev/null; then
    echo -e "  ${YELLOW}⚠${NC} Found hardcoded file paths (should use relative paths)"
    grep -rE "/Users/[a-zA-Z]+/" app/ 2>/dev/null | grep -v ".git" | grep -v ".pyc" | head -3
    ((WARNINGS++))
else
    echo -e "  ${GREEN}✓${NC} No hardcoded file paths found"
fi

echo ""
echo "🔧 Checking configuration..."

# Check .env.example has required vars
REQUIRED_VARS=("ALPACA_API_KEY" "ALPACA_SECRET_KEY" "FINNHUB_API_KEY" "SUPABASE_URL" "SUPABASE_KEY" "OPENROUTER_API_KEY")
for var in "${REQUIRED_VARS[@]}"; do
    if grep -q "$var" .env.example; then
        echo -e "  ${GREEN}✓${NC} .env.example has $var"
    else
        echo -e "  ${RED}✗${NC} .env.example missing $var"
        ((ERRORS++))
    fi
done

# Check run.sh is executable
if [ -x "run.sh" ]; then
    echo -e "  ${GREEN}✓${NC} run.sh is executable"
    else
    echo -e "  ${YELLOW}⚠${NC} run.sh is not executable (run: chmod +x run.sh)"
    ((WARNINGS++))
fi

echo ""
echo "📋 Summary"
echo "=========="
echo "Total errors: $ERRORS"
echo "Total warnings: $WARNINGS"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Ready for deployment.${NC}"
    exit 0
else
    echo -e "${RED}✗ Please fix errors before deployment.${NC}"
    exit 1
fi
