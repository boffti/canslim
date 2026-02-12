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
    "PROJECT_SUMMARY.md"
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
SENSITIVE_PATTERNS=(
    "1aFUHj4TsRCcUTQqXD6wfV6Jbi8uyJ1fhuFKouVEhdA4"
    "google-sheet@openclaw-gmail"
    "535000"
    "/Users/michaelgranit/"
)

for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    # Check in app/ directory recursively
    if grep -r "$pattern" app/ 2>/dev/null | grep -v ".git" > /dev/null; then
        echo -e "  ${RED}✗${NC} Found sensitive data: $pattern"
        ((ERRORS++))
    else
        echo -e "  ${GREEN}✓${NC} No $pattern found"
    fi
done

echo ""
echo "🔧 Checking configuration..."

# Check .env.example has required vars
REQUIRED_VARS=("GOOGLE_SHEET_ID" "GOG_ACCOUNT" "SUPABASE_URL" "SUPABASE_KEY" "GEMINI_API_KEY")
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
