# RepoKit Adoption Guide: Transform Your Code into Professional Repositories

This guide walks you through adopting RepoKit for your existing projects, from simple local organization to full GitHub deployment.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Before You Begin](#before-you-begin)
3. [Basic Adoption Tutorial](#basic-adoption-tutorial)
4. [GitHub Deployment Tutorial](#github-deployment-tutorial)
5. [Advanced Adoption Scenarios](#advanced-adoption-scenarios)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

## 🚀 Quick Start

**Test first** (always recommended):
```bash
repokit adopt ./my-project --dry-run -vv
```

**Basic adoption**:
```bash
repokit adopt ./my-project --backup
```

**Full GitHub deployment**:
```bash
repokit adopt ./my-project --publish-to github --repo-name my-project --private-repo
```

## 🔍 Before You Begin

### Prerequisites
- Git installed on your system
- Python 3.10+ with RepoKit installed (`pip install git-repokit`)
- GitHub account (if publishing to GitHub)
- Your project in a folder somewhere on your computer

### Understanding What Adoption Does

RepoKit adoption:
- ✅ **Preserves all your existing code** - Nothing is deleted or lost
- ✅ **Adds professional structure** - Creates organized directories
- ✅ **Sets up Git branches** - Organizes your development workflow
- ✅ **Protects sensitive files** - Keeps private stuff private
- ✅ **Optionally publishes to GitHub** - Professional online presence

### What You'll Get

After adoption, your project will have:
```
my-project/
├── local/          # Your private development workspace (private branch)
├── github/         # Clean version for GitHub (main branch)  
├── dev/            # Development workspace (dev branch)
└── .git/           # Git repository with professional structure
```

## 📖 Basic Adoption Tutorial

### Step 1: Prepare Your Project

**Navigate to your project**:
```bash
cd /path/to/your/project
```

**Check what you have**:
```bash
ls -la
# Look for .git folder, existing code files, any sensitive files
```

### Step 2: Test the Adoption (Recommended)

**Run a dry-run** to see what would happen:
```bash
repokit adopt . --dry-run --verbose
```

This shows you:
- What directories will be created
- Which files are considered sensitive
- What the final structure will look like
- No changes are made to your project

### Step 3: Create a Backup (Recommended)

**Automatic backup**:
```bash
repokit adopt . --backup --backup-location ../my-project-backup
```

**Manual backup**:
```bash
cp -r ../my-project ../my-project-backup-$(date +%Y%m%d)
```

### Step 4: Basic Adoption

**Minimal adoption** (just add structure):
```bash
repokit adopt .
```

**Adoption with language detection**:
```bash
repokit adopt . --language python --description "My Python project"
```

**Adoption with directory profile**:
```bash
repokit adopt . --dir-profile standard --language python
```

### Step 5: Verify the Results

**Check the new structure**:
```bash
ls -la
# You should see: local/, github/, dev/ directories

ls local/
# Your code is here, now organized

git branch
# You should see: private, main, dev branches
```

**Test switching between branches**:
```bash
cd local
git log --oneline
# Shows your development history

cd ../github  
git log --oneline
# Shows clean public history
```

## 🌐 GitHub Deployment Tutorial

### Step 1: Prepare for GitHub

**Ensure you have GitHub credentials**:
```bash
gh auth status
# or
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Step 2: Choose Your Deployment Strategy

**Public repository**:
```bash
repokit adopt ./my-project \
  --publish-to github \
  --repo-name my-awesome-project \
  --language python \
  --description "My awesome Python project"
```

**Private repository**:
```bash
repokit adopt ./my-project \
  --publish-to github \
  --repo-name my-private-project \
  --private-repo \
  --language python
```

**Organization repository**:
```bash
repokit adopt ./my-project \
  --publish-to github \
  --repo-name team-project \
  --organization mycompany \
  --private-repo
```

### Step 3: Full GitHub Deployment (Real Example)

Here's the exact command used for the UNCtools project:
```bash
repokit adopt ./unctools-project \
  --branch-strategy simple \
  --migration-strategy safe \
  --dir-profile standard \
  --language python \
  --description "Universal Naming Convention (UNC) path tools for Python" \
  --publish-to github \
  --repo-name UNCtools \
  --private-repo \
  --ai claude \
  --backup \
  --backup-location ../unctools-backup-before-adoption
```

**What this does**:
- Creates simple branch structure (main, dev, private)
- Uses safe migration (preserves everything)
- Sets up standard directories
- Configures for Python project
- Publishes to GitHub as private repository
- Adds Claude AI integration
- Creates backup before starting

### Step 4: Verify GitHub Deployment

**Check local structure**:
```bash
cd my-project/github
git remote -v
# Should show GitHub repository URL

git log --oneline
# Should show clean commit history
```

**Check GitHub**:
1. Go to your GitHub profile
2. Find the new repository
3. Verify it looks professional and contains no sensitive files

## 🎯 Advanced Adoption Scenarios

### Scenario 1: Data Science Project

```bash
repokit adopt ./data-science-project \
  --directories "data,notebooks,models,experiments" \
  --private-dirs "experiments,drafts" \
  --sensitive-patterns "*.csv,*.pkl,data/*,*.ipynb_checkpoints" \
  --language python \
  --dir-profile complete
```

### Scenario 2: Web Application

```bash
repokit adopt ./my-webapp \
  --branch-strategy gitflow \
  --language javascript \
  --directories "src,public,tests,docs" \
  --publish-to github \
  --repo-name my-webapp
```

### Scenario 3: Open Source Library

```bash
repokit adopt ./my-library \
  --dir-profile complete \
  --language python \
  --publish-to github \
  --repo-name my-open-source-lib \
  --description "An awesome open source library" \
  --ai claude
```

### Scenario 4: Company Project with History Cleaning

```bash
repokit adopt ./legacy-project \
  --clean-history \
  --cleaning-recipe pre-open-source \
  --backup \
  --private-repo \
  --organization mycompany
```

### Scenario 5: Research Project

```bash
repokit adopt ./research-project \
  --directories "papers,datasets,analysis,figures" \
  --private-dirs "drafts,reviews,notes" \
  --sensitive-files "api_keys.txt,credentials.json" \
  --ai claude \
  --private-repo
```

## 🛠️ Troubleshooting

### Common Issues and Solutions

#### Issue: "Permission denied" errors
**Solution**:
```bash
chmod -R u+w ./my-project
repokit adopt ./my-project
```

#### Issue: Git repository already exists
**Solution**:
```bash
# RepoKit handles existing git repos, but if you get errors:
cd my-project
git status  # Check current state
repokit adopt . --migration-strategy safe
```

#### Issue: Sensitive files detected in public branch
**Solution**:
```bash
# Add patterns to exclude them
repokit adopt . --sensitive-patterns "*.env,secrets/*,private_notes.txt"
```

#### Issue: GitHub authentication failed
**Solution**:
```bash
# Set up GitHub CLI
gh auth login

# Or use token
repokit adopt . --publish-to github --token your_github_token
```

#### Issue: Large files causing problems
**Solution**:
```bash
# Use git LFS for large files
git lfs track "*.csv"
git lfs track "*.pkl"
repokit adopt .
```

### Recovery Procedures

#### If adoption goes wrong:
```bash
# Restore from backup
rm -rf my-project
cp -r my-project-backup my-project

# Or reset git state
cd my-project/local
git reset --hard HEAD~1  # Go back one commit
```

#### If GitHub deployment fails:
```bash
# Deployment can be re-run
cd my-project/local
repokit adopt . --publish-to github --repo-name my-project-fixed
```

## 📚 Best Practices

### Before Adoption

1. **Always test first**: Use `--dry-run` to preview changes
2. **Create backups**: Use `--backup` or manual copy
3. **Clean up first**: Remove obvious junk files manually
4. **Check for secrets**: Look for API keys, passwords, tokens

### During Adoption

1. **Use descriptive names**: Good repository names help discovery
2. **Choose appropriate visibility**: Private for personal/company, public for open source
3. **Pick the right language**: Helps RepoKit choose appropriate templates
4. **Select proper directory profile**: Minimal for simple projects, complete for complex ones

### After Adoption

1. **Verify the structure**: Check that everything looks right
2. **Test the workflow**: Try making changes in different branches
3. **Update documentation**: Add proper README, usage examples
4. **Configure CI/CD**: Set up automated testing and deployment

### Sensitive File Management

**Common sensitive files to protect**:
```bash
--sensitive-patterns ".env,.env.*,*.key,*.pem,secrets/*,private/*,*.log,*~"
```

**Common sensitive file patterns**:
- `.env*` - Environment variables
- `*.key`, `*.pem` - Certificates and keys
- `secrets/*` - Secret directories
- `private/*` - Private directories
- `*.log` - Log files
- `*~` - Vim backup files
- `*.bak` - Backup files

### Branch Strategy Guide

**Simple** (recommended for most projects):
- `private` - Your personal workspace
- `dev` - Development and testing
- `main` - Clean public version

**GitFlow** (for complex projects with releases):
- `private` - Personal workspace
- `develop` - Main development
- `feature/*` - Feature branches
- `release/*` - Release preparation
- `main` - Stable releases

**GitHub Flow** (for continuous deployment):
- `private` - Personal workspace
- `main` - Always deployable
- `feature/*` - Feature branches

## 🎉 Success Stories

### Before and After Examples

**Before**:
```
messy-project/
├── script.py
├── script_old.py
├── script_backup.py
├── test.py
├── data.csv
├── api_key.txt
├── TODO.txt
└── random_notes.md
```

**After**:
```
messy-project/
├── local/              # Private development
│   ├── src/script.py
│   ├── tests/test.py
│   ├── private/notes.md
│   └── private/api_key.txt
├── github/             # Public GitHub version
│   ├── README.md
│   ├── src/script.py
│   ├── tests/test.py
│   └── requirements.txt
└── dev/                # Development workspace
```

### Real Project: UNCtools

**Before**: Python utility scripts scattered in a folder
**After**: Professional Python package on GitHub with:
- Clean structure and documentation
- Automated testing setup
- Professional GitHub templates
- Sensitive file protection
- Ready for PyPI publication

**Command used**:
```bash
repokit adopt ./unctools \
  --branch-strategy simple \
  --dir-profile standard \
  --language python \
  --publish-to github \
  --repo-name UNCtools \
  --private-repo \
  --ai claude
```

**Result**: Professional repository that's maintainable, shareable, and deployment-ready.

## 📞 Getting Help

- **Documentation**: Check other files in `docs/` directory
- **Examples**: See `repokit adopt --help` for more examples
- **Issues**: Check project issues on GitHub
- **Verbose output**: Use `-vv` flag for detailed logging

---

**Next Steps**: Once you've adopted your project, check out [Branch-Strategies.md](./Branch-Strategies.md) to understand how to use your new workflow effectively.