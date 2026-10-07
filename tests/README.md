# RepoKit Test Suite

Comprehensive testing framework for RepoKit functionality including unit tests, integration tests, and end-to-end GitHub deployment tests.

## Quick Start

```bash
# Run the suite (from the project root)
python -m pytest

# Also run the live GitHub tests -- these create real repositories
REPOKIT_LIVE_GITHUB=1 python -m pytest
```

The suite is isolated from your own setup by `tests/conftest.py`: git never signs the commits tests make, `HOME`/`USERPROFILE` point at a temporary directory (so `~/.repokit/credentials.json` is never touched), and GitHub tokens are blanked. Tests marked `live` are skipped, and `.env.test` is not read, unless `REPOKIT_LIVE_GITHUB=1` is set.

> **Note:** `tests/run_tests.py` and the commands below do not currently run: the test modules use package-relative imports, which the runner's top-level imports cannot load (`ImportError: attempted relative import with no known parent package`). Use `python -m pytest`.

```bash
# Run all tests
python tests/run_tests.py

# Run only unit tests (no GitHub token required)
python tests/run_tests.py --unit

# Run integration tests
python tests/run_tests.py --integration

# Run GitHub deployment tests (requires token)
python tests/run_tests.py --github

# Check test environment setup
python tests/run_tests.py --check
```

## Test Categories

### Unit Tests
- **No external dependencies** - Test core functionality in isolation
- **Fast execution** - Run in seconds
- **No GitHub token required**

Tests included:
- `test_core_functionality.py` - Core components (ProjectAnalyzer, GitManager, Config, etc.)

### Integration Tests
- **Test CLI commands** - Verify command-line interface works correctly
- **Local operations only** - No GitHub API calls
- **Medium speed** - Run in under a minute

Tests included:
- `test_cli_integration.py` - CLI commands and workflows

### GitHub Tests
- **Require GitHub token** - Test real GitHub API integration
- **Create real repositories** - Auto-cleaned after tests
- **Slower execution** - Network operations

Tests included:
- `test_github_integration.py` - GitHub API and credential management
- `test_deployment_scenarios.py` - Complete deployment scenarios from docs

## Setup

### 1. Install RepoKit in Development Mode
```bash
pip install -e ".[dev]"
```

### 2. Configure GitHub Token (for GitHub tests)

Create `.env.test` file in the project root:
```bash
# .env.test
REPOKIT_TEST_GITHUB_TOKEN=your_github_personal_access_token_here
REPOKIT_TEST_GITHUB_USER=your-github-username  # Optional
REPOKIT_TEST_CLEANUP=true  # Auto-cleanup test repos
REPOKIT_TEST_PREFIX=repokit-test-  # Test repo prefix
```

**Important**: The `.env.test` file is already in `.gitignore` and should NEVER be committed! It is read only when `REPOKIT_LIVE_GITHUB=1` is set.

### 3. Get a GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scope: `repo` (full repository access)
4. Copy the token to `.env.test`

## Running Tests

### Run All Tests
```bash
python tests/run_tests.py
```

### Run Specific Categories
```bash
# Fast unit tests only
python tests/run_tests.py --unit

# Integration tests (CLI testing)
python tests/run_tests.py --integration

# GitHub API tests (requires token)
python tests/run_tests.py --github

# Deployment scenarios only
python tests/run_tests.py --deployment
```

### Test Options
```bash
# Verbose output
python tests/run_tests.py --verbose

# Skip cleanup (leave test repos on GitHub)
python tests/run_tests.py --no-cleanup

# Check environment setup
python tests/run_tests.py --check
```

### Run Specific Test Files
```bash
# Using pytest (if installed)
pytest tests/test_core_functionality.py

# Using unittest directly
python -m unittest tests.test_core_functionality

# Run specific test class
python -m unittest tests.test_core_functionality.TestProjectAnalyzer

# Run specific test method
python -m unittest tests.test_core_functionality.TestProjectAnalyzer.test_detect_python_project
```

## Test Structure

### Test Files

- **`test_utils.py`** - Shared test utilities and base classes
  - `RepoKitTestCase` - Base class with helper methods
  - `TestConfig` - Test configuration
  - `GitHubTestCleanup` - Auto-cleanup for GitHub repos
  - `@requires_github_token` - Decorator to skip tests without token

- **`test_core_functionality.py`** - Unit tests for core components
  - `TestProjectAnalyzer` - Project analysis logic
  - `TestGitManager` - Git operations
  - `TestConfig` - Configuration system
  - `TestTemplateEngine` - Template rendering
  - `TestDirectoryAnalyzer` - Directory analysis

- **`test_cli_integration.py`** - Integration tests for CLI
  - `TestCLICommands` - Basic command functionality
  - `TestComplexWorkflows` - Multi-step workflows
  - `TestErrorHandling` - Error cases and edge conditions

- **`test_github_integration.py`** - GitHub API tests
  - `TestGitHubIntegration` - Real API integration
  - `TestGitHubAPIMocking` - Mock API testing
  - `TestCredentialManagement` - Credential storage

- **`test_deployment_scenarios.py`** - End-to-end deployment tests
  - Tests all scenarios from `docs/Deployment-Demo.md`
  - Demo 1: Brand new project
  - Demo 2: Existing Python project
  - Demo 3: Complex multi-branch project
  - Demo 4: Legacy project migration

## Writing New Tests

### Example Unit Test
```python
class TestNewFeature(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_feature_behavior(self):
        # Test implementation
        result = my_function()
        self.assertEqual(result, expected_value)
```

### Example Integration Test
```python
class TestNewCommand(RepoKitTestCase):
    def test_command_execution(self):
        stdout, stderr = self.assert_repokit_success([
            "new-command", "--option", "value"
        ])
        self.assertIn("expected output", stdout)
```

### Example GitHub Test
```python
class TestGitHubFeature(RepoKitTestCase):
    @requires_github_token
    def test_github_operation(self):
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        # Test GitHub operations
        # Cleanup happens automatically
```

## Test Environment Variables

- `REPOKIT_TEST_GITHUB_TOKEN` - GitHub personal access token
- `REPOKIT_TEST_GITHUB_USER` - GitHub username (optional)
- `REPOKIT_TEST_GITHUB_ORG` - GitHub organization for org tests (optional)
- `REPOKIT_TEST_CLEANUP` - Enable/disable auto-cleanup (default: true)
- `REPOKIT_TEST_PREFIX` - Prefix for test repository names

## Troubleshooting

### GitHub Token Issues
```bash
# Verify token is loaded
python tests/run_tests.py --check

# Test token manually
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
```

### Test Failures
```bash
# Run with verbose output
python tests/run_tests.py --verbose

# Run specific failing test
python -m unittest tests.test_name.TestClass.test_method -v
```

### Cleanup Issues
```bash
# Disable auto-cleanup to inspect repos
python tests/run_tests.py --no-cleanup

# Manually clean up test repos
# Go to GitHub and delete repos starting with "repokit-test-"
```

## Continuous Integration

For CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run RepoKit Tests
  env:
    REPOKIT_TEST_GITHUB_TOKEN: ${{ secrets.REPOKIT_TEST_TOKEN }}
  run: |
    pip install -e ".[dev]"
    python tests/run_tests.py
```

## Coverage

To run tests with coverage:

```bash
# Install coverage
pip install coverage

# Run with coverage
coverage run -m unittest discover tests

# Generate report
coverage report
coverage html  # Creates htmlcov/index.html
```

## Best Practices

1. **Always use test prefixes** - All test repos start with `repokit-test-`
2. **Register repos for cleanup** - Use `self.github_cleanup.register_repo()`
3. **Use helper methods** - Leverage `RepoKitTestCase` utilities
4. **Test both success and failure** - Include error cases
5. **Mock when possible** - Use `MockGitHubAPI` for unit tests
6. **Keep tokens secure** - Never commit `.env.test` or tokens

## Contributing Tests

When adding new features to RepoKit:

1. Add unit tests for new components
2. Add integration tests for new CLI commands
3. Add GitHub tests if feature involves deployment
4. Update test documentation
5. Ensure all tests pass before submitting PR

Happy testing! 🧪