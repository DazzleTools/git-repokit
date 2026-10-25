# RepoKit GitHub Deployment Demo

This is a step-by-step demonstration of how to use RepoKit's universal bootstrap system to create, migrate, and deploy projects to GitHub.

The demos adopt existing folders with `repokit adopt`, which uses the private-branch layout: your folder becomes the local checkout on the `private` branch, and the public branches are checked out as sibling folders (`github/` for `main`, `dev/` for `dev`). For a project you are starting from nothing, `repokit create` makes the default `main-only` layout instead; see the end of Demo 1 and [Branch-Strategies.md](Branch-Strategies.md).

## Prerequisites

1. **Install RepoKit**: `pip install git-repokit` (Python 3.10 or newer; also published as `dazzle-git-repokit`). The command is `repokit`.
2. **A license choice**: `create` needs `--license <id>` (`repokit list` ends with the ids) unless `~/.repokit/config.json` has a `license` key. `adopt` keeps the project's own license file, or writes the config's, or adopts without one. The demos use `--license mit`.
3. **GitHub access**, by one of two routes:
   - **The `gh` CLI, logged in** (`gh auth login`). This is the simple path and needs no token. It is used by `repokit create ... --github`.
   - **A personal access token** with `repo` permissions, for the `--publish-to github` path that `adopt`, `migrate`, `create` and `publish` share. Create one at https://github.com/settings/tokens (select the `repo` scope, and copy the token, you only see it once).

The demos below use the token path, because `adopt` has no `--github` flag.

## Demo 1: Brand New Project

Let's create a Python project from scratch and deploy it to GitHub:

```bash
# Step 1: Create a new project directory
mkdir awesome-calculator
cd awesome-calculator

# Step 2: Add some initial code
cat > main.py << 'EOF'
def add(a, b):
    """Add two numbers."""
    return a + b

def subtract(a, b):
    """Subtract two numbers."""
    return a - b

def main():
    print("Awesome Calculator!")
    print("2 + 3 =", add(2, 3))
    print("5 - 2 =", subtract(5, 2))

if __name__ == "__main__":
    main()
EOF

# Step 3: Add requirements
echo "# No external dependencies yet" > requirements.txt

# Step 4: Analyze what RepoKit will do
repokit analyze .

# Output should show:
# Project type: source_no_git
# Detected language: python
# Migration complexity: low
# Recommended strategy: safe
# Recommended branch strategy: simple

# Step 5: Store your GitHub token
repokit store-credentials --publish-to github --token "YOUR_GITHUB_TOKEN_HERE"

# Step 6: Adopt and deploy in one command!
repokit adopt . --license mit --language python --branch-strategy simple \
  --publish-to github --private-repo --ai claude

# This will:
# - Create the RepoKit directory structure
# - Initialize Git with the private, main and dev branches
# - Lay down the python layers and templates (because of --language python)
# - Add Claude AI integration
# - Create a private GitHub repository
# - Push main and dev to GitHub (never the private branch)
```

The analysis recommends the `simple` branch strategy, but `adopt` only uses it when you pass `--branch-strategy simple`; without the flag it uses `standard`.

**Expected Results:**
- New GitHub repository: `awesome-calculator`
- Local branches: `private`, `main`, `dev` (`private` is never pushed)
- `awesome-calculator/` stays on `private`; `../github/` has `main` and `../dev/` has `dev`
- The RepoKit structure with Python templates and a LICENSE
- Claude AI integration files
- All code preserved and properly organized

**If you are starting a project rather than adopting a folder**, skip all of this and let `create` do it. This makes the default layout (one `main` branch, a nested private repository, git-repokit-common's hooks), makes the GitHub repository through your `gh` login, and sets up the labels and Roadmap issue:

```bash
repokit create awesome-calculator --language python --license mit --github --github-setup labels,issues
```

See [GitHub-Setup.md](GitHub-Setup.md) for all the `--github-setup` steps and `--topics`.

## Demo 2: Existing Python Project

Let's migrate an existing Python project with some history:

```bash
# Step 1: Create a project with some Git history
mkdir weather-app
cd weather-app

# Initialize Git and create initial structure
git init
git config user.name "Demo User"
git config user.email "demo@example.com"

# Add some code
cat > weather.py << 'EOF'
import requests

def get_weather(city):
    """Get weather for a city (mock implementation)."""
    return f"Weather in {city}: Sunny, 25°C"

if __name__ == "__main__":
    city = input("Enter city: ")
    print(get_weather(city))
EOF

cat > requirements.txt << 'EOF'
requests>=2.28.0
EOF

# Create initial commits
git add .
git commit -m "Initial weather app"

# Add more features
mkdir tests
cat > tests/test_weather.py << 'EOF'
import unittest
from weather import get_weather

class TestWeather(unittest.TestCase):
    def test_get_weather(self):
        result = get_weather("London")
        self.assertIn("London", result)
        self.assertIn("°C", result)

if __name__ == "__main__":
    unittest.main()
EOF

git add tests/
git commit -m "Add basic tests"

# Step 2: Analyze the existing project
repokit analyze .

# Output should show:
# Detected language: python
# Migration complexity: medium
# Recommended strategy: safe
# Recommended branch strategy: simple
# Git repository: current branch and branches listed

# Step 3: Adopt preserving all Git history
repokit adopt . --license mit --language python --migration-strategy safe \
  --publish-to github --organization "your-org"

# This will:
# - Preserve all existing Git history and commits
# - Add RepoKit structure around existing files
# - Create the branches for the standard strategy
# - Deploy to your organization on GitHub
```

**Expected Results:**
- GitHub repository with the Git history preserved
- All existing commits and files intact
- Enhanced with the RepoKit structure
- Created under your organization

## Demo 3: Multi-Branch Project

Let's work with a project that already has several branches:

```bash
# Step 1: Create a project with branches
mkdir api-service
cd api-service

# Initialize with a branch structure
git init
git config user.name "Demo User"
git config user.email "demo@example.com"

# Create main application
cat > app.py << 'EOF'
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/api/version')
def version():
    return jsonify({'version': '1.0.0'})

if __name__ == '__main__':
    app.run(debug=True)
EOF

cat > requirements.txt << 'EOF'
Flask>=2.0.0
gunicorn>=20.0.0
EOF

# Initial commit on main
git add .
git commit -m "Initial API service"

# Create development branch with new features
git checkout -b develop
cat > auth.py << 'EOF'
def authenticate(token):
    """Simple token authentication."""
    return token == "valid-token"

def get_user_info(token):
    """Get user information from token."""
    if authenticate(token):
        return {"user": "demo", "role": "admin"}
    return None
EOF

git add auth.py
git commit -m "Add authentication module"

# Create feature branch
git checkout -b feature/user-management
mkdir models
cat > models/user.py << 'EOF'
class User:
    def __init__(self, username, email):
        self.username = username
        self.email = email
    
    def to_dict(self):
        return {
            'username': self.username,
            'email': self.email
        }
EOF

git add models/
git commit -m "Add user model"

# Go back to develop
git checkout develop

# Step 2: Analyze this project
repokit analyze .

# Output should show:
# Detected language: python
# Migration complexity: medium
# Recommended strategy: merge
# Recommended branch strategy: gitflow (detected existing pattern)
# Git repository: Branches: develop, feature/user-management, main

# Step 3: Adopt with the branch strategy the analysis suggested
repokit adopt . --license mit --language python --migration-strategy merge \
  --branch-strategy gitflow --publish-to github

# This will:
# - Keep all existing branches
# - Add the gitflow branches that are missing (private, release, hotfix)
# - Add the RepoKit structure, merging with files that exist
# - Publish the public branches to GitHub
```

**Expected Results:**
- All existing branches preserved
- Git history maintained
- RepoKit structure added
- The branch strategy you chose, matching the pattern the analysis detected

`adopt` does not pick the branch strategy for you; read the recommendation from `analyze` and pass it with `--branch-strategy`.

## Demo 4: Legacy Project Migration

Migrate a legacy project with files that overlap RepoKit's templates:

```bash
# Step 1: Create a "legacy" project with potential conflicts
mkdir legacy-tool
cd legacy-tool

# Create files that might conflict with RepoKit templates
cat > setup.py << 'EOF'
# Legacy setup.py with custom configuration
from setuptools import setup, find_packages

setup(
    name="legacy-tool",
    version="0.1.0",
    packages=find_packages(),
    # Custom legacy configuration here
    custom_legacy_setting=True,
)
EOF

mkdir -p .github/workflows
cat > .github/workflows/old-ci.yml << 'EOF'
# Legacy CI configuration
name: Old CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run legacy tests
        run: echo "Legacy testing approach"
EOF

# Add source code
mkdir src
cat > src/legacy_app.py << 'EOF'
"""Legacy application with old patterns."""

class LegacyProcessor:
    def __init__(self):
        self.data = []
    
    def process(self, item):
        # Old processing logic
        self.data.append(item.upper())
        return self.data

def main():
    processor = LegacyProcessor()
    processor.process("hello")
    processor.process("world")
    print("Processed:", processor.data)

if __name__ == "__main__":
    main()
EOF

# Step 2: Initialize Git
git init
git config user.name "Demo User"
git config user.email "demo@example.com"
git add .
git commit -m "Legacy codebase"

# Step 3: Analyze for migration conflicts
repokit analyze .

# Output should show:
# Detected language: python
# Migration complexity: medium
# Has template conflicts: Yes
# Recommended strategy: merge

# Step 4: Preview, then adopt with the safe migration strategy
repokit adopt . --license mit --language python --migration-strategy safe \
  --backup --dry-run

# See what would happen first, then run it for real
repokit adopt . --license mit --language python --migration-strategy safe \
  --backup --publish-to github

# This will:
# - Copy the whole project to a backup folder first (--backup)
# - Keep your setup.py and .github/workflows/old-ci.yml as they are
# - Add the RepoKit and python files (pyproject.toml, the CI workflows) alongside
# - Copy any template-directory files that conflict into a "<dir>_backup" folder
```

Safe means your own files are never overwritten. Where a RepoKit template would land on an existing file, safe keeps yours; conflicting files from a template directory such as `.github` are copied to a `_backup` folder (for example `.github_backup/`) when RepoKit has to move them aside. Use `--migration-strategy merge` to combine configuration files, or `replace` to take RepoKit's versions.

**Expected Results:**
- A backup copy of the project, beside it (`legacy-tool_backup_<timestamp>`)
- Legacy files kept; new RepoKit files added
- No existing functionality broken

## Authentication Methods Demo

### Method 1: Environment Variable
```bash
# Set token in environment
export GITHUB_TOKEN="your_token_here"

# Deploy using environment token
repokit adopt my-project --license mit --publish-to github
```

### Method 2: Stored Credentials
```bash
# Store token (one time; saved in ~/.repokit/credentials.json)
repokit store-credentials --publish-to github --token "your_token_here"

# Deploy using stored credentials (no token needed)
repokit adopt my-project --license mit --publish-to github
```

### Method 3: Password Manager Integration
```bash
# Using pass password manager
repokit adopt my-project --license mit --publish-to github --token-command "pass show github/token"

# Using 1Password CLI
repokit adopt my-project --license mit --publish-to github --token-command "op read op://Personal/GitHub/token"

# Using LastPass CLI
repokit adopt my-project --license mit --publish-to github --token-command "lpass show --password github-token"
```

### Method 4: Organization Deployment
```bash
# Store a default organization with the credentials
repokit store-credentials --publish-to github --token "org_token" --organization "my-company"

# Deploy to organization
repokit adopt my-project --license mit --publish-to github --organization "my-company"
```

### Method 5: The `gh` CLI (create only)
```bash
# No token handling: uses your gh login
gh auth login
repokit create my-project --license mit --github
```

See [Auth-Guide.md](Auth-Guide.md) for details on tokens and scopes.

## Advanced Deployment Options

### Private Repository with Description
```bash
repokit adopt my-project \
  --license mit \
  --publish-to github \
  --private-repo \
  --description "My awesome project built with RepoKit"
```

### Full Automation with All Options
```bash
repokit adopt my-project \
  --license mit \
  --language python \
  --migration-strategy safe \
  --branch-strategy simple \
  --publish-to github \
  --private-repo \
  --organization "my-company" \
  --ai claude \
  --description "Production-ready application"
```

### Multiple Projects Batch Deployment
```bash
# Deploy multiple projects
for project in project1 project2 project3; do
  echo "Deploying $project..."
  repokit adopt $project --license mit --publish-to github --migration-strategy safe
done
```

## Troubleshooting Common Issues

### Issue 1: Token Authentication Fails
```bash
# Verify a token is stored (the file holds the token: do not share it)
ls ~/.repokit/credentials.json

# Test token manually
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user

# Re-store credentials if needed
repokit store-credentials --publish-to github --token "new_token"
```

### Issue 2: Repository Already Exists
```bash
# RepoKit will show an error like:
# "Repository already exists at https://github.com/user/project"

# Solutions:
# 1. Use a different name for the GitHub repository
repokit adopt my-project --license mit --publish-to github --repo-name "my-project-v2"

# 2. Delete the existing repository first (careful!)
# 3. Push to the existing repository (if you own it)
```

### Issue 3: Uncommitted Changes
```bash
# RepoKit detects uncommitted changes and warns you
# Commit changes first:
git add .
git commit -m "Save work before RepoKit adoption"

# Then proceed with adoption
repokit adopt . --license mit --publish-to github
```

### Issue 4: Template Conflicts
```bash
# Use safe strategy to preserve existing files
repokit adopt my-project --license mit --migration-strategy safe --publish-to github

# Or use merge strategy to combine configurations
repokit adopt my-project --license mit --migration-strategy merge --publish-to github

# Check the backup folders created
ls -d *_backup .*_backup
```

### Issue 5: "no license named"
`create` stops with `no license named: pass --license <id>...` until a license is chosen. Add `--license mit` (or `file=PATH`, or `none`), or set `license` once in `~/.repokit/config.json` (see [Configuration.md](Configuration.md)). `adopt` never stops for this: it keeps the project's own license file, writes the config's license when there is none, or adopts the project without one and says so.

## Success Verification

After deployment, verify everything worked:

```bash
# Check GitHub repository was created
# Visit: https://github.com/your-username/your-project

# Verify local repository
git remote -v
git branch -a
git worktree list      # the project folder on private, plus the github/ and dev/ worktrees

# Check RepoKit structure
ls -la
# Should see: docs/, private/, scripts/, tests/, etc.

# Verify branches were pushed (main and dev, never private)
git ls-remote origin

# Test the application still works
python main.py  # or your app's entry point
```

## Next Steps After Deployment

1. **Review Generated Templates**: Check and customize the generated files
2. **Set Up CI/CD**: Configure GitHub Actions workflows
3. **Add Collaborators**: Invite team members to the repository
4. **Configure Branch Protection**: Set up branch protection rules
5. **Update Documentation**: Customize README and docs for your project

## Example Script

Here is a script you can run to try RepoKit's analysis and dry run (it creates a folder and publishes nothing):

```bash
#!/bin/bash
# RepoKit Deployment Test Script

set -e  # Exit on any error

echo "=== RepoKit GitHub Deployment Demo ==="

# Create test project
mkdir repokit-demo-test
cd repokit-demo-test

# Add sample code
cat > calculator.py << 'EOF'
def calculate(operation, a, b):
    """Simple calculator function."""
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        return a / b if b != 0 else "Cannot divide by zero"
    else:
        return "Unknown operation"

def main():
    print("RepoKit Demo Calculator")
    print("2 + 3 =", calculate("add", 2, 3))
    print("10 - 4 =", calculate("subtract", 10, 4))
    print("5 * 6 =", calculate("multiply", 5, 6))
    print("15 / 3 =", calculate("divide", 15, 3))

if __name__ == "__main__":
    main()
EOF

echo "# RepoKit Demo Calculator" > README.md
echo "# No external dependencies" > requirements.txt

echo "1. Analyzing project..."
repokit analyze .

echo "2. Testing dry run..."
repokit adopt . --license mit --language python --dry-run

echo "3. Ready for GitHub deployment!"
echo "   Run: repokit store-credentials --publish-to github --token YOUR_TOKEN"
echo "   Then: repokit adopt . --license mit --language python --publish-to github --private-repo"
echo ""
echo "Demo project created in: $(pwd)"
```

Save this as `demo.sh`, make it executable with `chmod +x demo.sh`, and run it to see what RepoKit would do. Delete the `repokit-demo-test` folder when you are done.

## Summary

RepoKit's universal bootstrap system provides:

- **Project analysis**: Reads the project type, language and Git state, and recommends a migration strategy and a branch strategy
- **Safe migration**: Preserves existing code and Git history
- **One-command deployment**: `--publish-to github`, or `create --github` through the `gh` CLI
- **Several token methods**: `GITHUB_TOKEN`, stored credentials, a token command
- **Standard repository structure**: directories, files, license and hooks
- **AI integration**: Claude files by default, `--ai none` to skip

Whether you are starting fresh or migrating legacy projects, RepoKit sets up the repository structure and the GitHub deployment in one command.
