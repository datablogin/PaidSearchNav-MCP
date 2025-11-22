#!/bin/bash

# Simple test script to debug Claude CLI issues
set -e

echo "=== Claude CLI Debug Test ==="

# Test 1: Basic Claude CLI functionality
echo "Test 1: Basic Claude CLI test"
echo "Hello Claude, please respond with 'SUCCESS'" | claude chat
echo ""

# Test 2: Claude CLI with file input
echo "Test 2: File input test"
cat > test_input.txt << 'EOF'
Please review this simple code:
```python
def hello():
    print("Hello World")
```
Provide brief feedback on code quality.
EOF

echo "Testing Claude with file input..."
claude chat < test_input.txt

echo ""
echo "Test 3: Environment check"
echo "Claude version: $(claude --version)"
echo "Working directory: $(pwd)"
echo "User: $(whoami)"

# Cleanup
rm -f test_input.txt

echo ""
echo "=== Debug test completed ==="