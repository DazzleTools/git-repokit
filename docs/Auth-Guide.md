# Authentication Guide for Remote Integration

RepoKit can publish repositories directly to GitHub or GitLab. There are two ways to do it, and they authenticate differently:

| Path | Flag | Authenticates with | Hosts |
|------|------|--------------------|-------|
| GitHub CLI | `--github` | your `gh` login; no token | GitHub |
| REST API | `--publish-to github` or `--publish-to gitlab` | a personal access token | GitHub, GitLab |

Use `--github` for GitHub unless you need a token (a machine without `gh`, for example). Use `--publish-to` for GitLab, which `--github` does not cover. This guide covers both, then how to store a token securely.

## GitHub with the gh CLI (no token)

Install the [GitHub CLI](https://cli.github.com) and log in once:

```bash
gh auth login
gh auth status
```

Then add `--github` to `create`:

```bash
# A private repository on your account, with the public branches pushed
repokit create my-project --license mit --github

# Public instead of private
repokit create my-project --license mit --github --public

# Under an organization
repokit create my-project --license mit --github --org your_org_name

# Build the local repository only; with --no-push nothing is created on GitHub
repokit create my-project --license mit --github --no-push
```

RepoKit never sees a token on this path; `gh` holds the login. The repository is private unless you pass `--public`. If your configuration names a GitHub username (`github.username`) and `gh` is logged into a different account, RepoKit refuses and tells you to run `gh auth switch` or fix the configuration. Only the public branches are pushed; a `private` branch never leaves your machine.

`--github-setup` can also set up labels, the Roadmap and Quick Notes issues, a pinned issue, discussions, topics, a PyPI environment and traffic tracking on the new repository. See [GitHub-Setup.md](./GitHub-Setup.md) for the whole `--github` path, including `--github-setup`.

## GitHub with a Token (--publish-to github)

### 1. Creating a Personal Access Token (PAT)

1. Go to your GitHub account settings
2. Select at the bottom on the left "Developer settings" → "Personal access tokens" → "Tokens (classic)"
3. Click "Generate new token"
4. Give your token a descriptive name (e.g., "RepoKit Integration")
5. Select the following scopes:
   - `repo` (Full control of private repositories)
   - `workflow` (if you plan to use GitHub Actions)
6. Click "Generate token"
7. **IMPORTANT**: Copy your token immediately! GitHub will only show it once.

### 2. Using Your Token with RepoKit

Once you have your GitHub token, there are several ways to give it to RepoKit. When more than one is present, RepoKit uses the first it finds in this order: `--token-command`, then the `GITHUB_TOKEN` environment variable, then the credentials file. (`--token TOKEN` also exists, but it puts the token in your shell history and process list; prefer the others.)

#### Option A: Environment Variable (Recommended)

Set the `GITHUB_TOKEN` environment variable:

```bash
# On Linux/macOS
export GITHUB_TOKEN=your_token_here

# On Windows (Command Prompt)
set GITHUB_TOKEN=your_token_here

# On Windows (PowerShell)
$env:GITHUB_TOKEN="your_token_here"
```

For permanent storage, add this to your shell profile (~/.bashrc, ~/.zshrc, etc.).

#### Option B: Credentials File

Let RepoKit write the file for you (it restricts the file to your user where the platform allows):

```bash
repokit store-credentials --publish-to github --token your_token_here
repokit store-credentials --publish-to github --token-command "pass show github/repokit-token"
repokit store-credentials --publish-to github --organization your_org_name
```

The default file is `~/.repokit/credentials.json`; `--credentials-file FILE` picks another. Stored credentials are used automatically when you publish. Or create the JSON file by hand:

```json
{
  "github": {
    "token": "your_token_here",
    "organization": "optional_organization_name"
  },
  "gitlab": {
    "token": "your_gitlab_token_here",
    "group": "optional_group_name"
  }
}
```

To use a file in a non-default place:

```bash
repokit create my-project --license mit --credentials-file ~/.repokit/credentials.json --publish-to github
```

**IMPORTANT**: Never commit this file to a repository!

#### Option C: Password Manager Integration

For advanced users, integrate with a password manager:

```bash
# Example with pass (Unix password manager)
repokit create my-project --license mit --token-command "pass show github/repokit-token" --publish-to github
```

## GitLab Authentication

### 1. Creating a Personal Access Token

1. Go to your GitLab account → "Preferences"
2. Select "Access Tokens"
3. Create a token with the following scopes:
   - `api` (API access)
   - `write_repository` (Repository write access)
4. Click "Create personal access token"
5. Copy your token immediately!

### 2. Using Your Token with RepoKit

Use your GitLab token in the same ways as GitHub (`--token-command`, environment variable, credentials file):

#### Environment Variables

```bash
export GITLAB_TOKEN=your_token_here
# Optional: Specify a custom GitLab instance
export GITLAB_API_URL=https://gitlab.example.com/api/v4
# Optional: a default group
export GITLAB_GROUP=your_group_name
```

For GitHub, the matching optional variables are `GITHUB_ORGANIZATION` (a default organization) and `GITHUB_API_URL` (GitHub Enterprise).

#### Credentials File

Same as GitHub (see above).

## Security Best Practices

1. **Prefer `--github`** for GitHub: with the `gh` login there is no token to store or leak
2. **Use environment variables** when possible to avoid storing tokens in files
3. **Set restrictive permissions** on any file containing tokens:
   ```bash
   chmod 600 ~/.repokit/credentials.json
   ```
4. **Never commit credential files** to repositories
5. **Use .gitignore** to prevent accidental commits:
   ```
   # Add to .gitignore
   *credentials*.json
   *.repokit-credentials
   ```
6. **Rotate tokens periodically** for enhanced security
7. **Use scoped tokens** with only the permissions needed
8. **Consider using a secrets manager** for team environments

## Using Authentication

Once you've set up authentication, you can use it to:

### Create and Publish Repositories

`create` needs a license (`--license`, or a `license` in your global configuration). The examples use `mit`.

```bash
# Create a new repository and publish it to GitHub
repokit create my-project --language python --license mit --publish-to github

# Create a private repository in an organization
repokit create my-project --language python --license mit --publish-to github --private-repo --organization your_org_name
```

Without `--private-repo`, `--publish-to` creates a public repository; `--github` is the other way round and creates a private one unless you pass `--public`.

### Publish Existing Repositories

```bash
# Publish an existing repository to GitHub
repokit publish ./my-existing-project --publish-to github

# Private, in an organization or group
repokit publish ./my-existing-project --publish-to github --private-repo --organization your_org_name
```

`publish` and `adopt` use the token path; `--github` is a `create` option.

### Generate a Bootstrap Script

```bash
# Generate a self-contained script that creates a RepoKit project and publishes it
repokit bootstrap --name myproject --service github --output bootstrap_repokit.py
```

## Troubleshooting

For `--github`: run `gh auth status` to see whether you are logged in and as whom, and use `gh auth login` or `gh auth switch` as needed. If RepoKit says the logged-in account differs from the configured `github.username`, switch accounts or correct the configuration.

For `--publish-to`, if you encounter authentication issues:

1. Verify your token has the correct permissions
   - For GitHub: repo, workflow (if using GitHub Actions)
   - For GitLab: api, write_repository
2. Check that the token hasn't expired
3. Ensure environment variables are properly set
4. Try the verbose flag for detailed error messages; it goes before the command name
   ```bash
   repokit -vvv create my-project --license mit --publish-to github
   ```
5. Verify network connectivity to the Git hosting service
6. Check that your organization/group name is correct

## Command Reference

```
repokit store-credentials --publish-to SERVICE [--token TOKEN] [--token-command COMMAND] [--organization ORG] [--credentials-file FILE]
```

Arguments:
- `--publish-to`: Service to use (github or gitlab)
- `--token`: Authentication token
- `--token-command`: Command to retrieve token
- `--organization`: Default organization or group name
- `--credentials-file`: Custom path for credentials file

`--verbose` / `-v` belongs to `repokit` itself and goes before the command (`repokit -v store-credentials ...`).

For more help, see the [GitHub token documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) or [GitLab token documentation](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html).
