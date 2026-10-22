# Plugin checkouts, measured

## claude-bookmarks

```json
{
 "repo": "claude-bookmarks",
 "root": [
  ".claude-plugin/",
  ".github/",
  ".gitignore",
  ".repokit-common.toml",
  ".repokit.json",
  "CHANGELOG.md",
  "CONTRIBUTING.md",
  "docs/",
  "LICENSE",
  "plugin/",
  "PRIVACY.md",
  "README.md",
  "ROADMAP.md",
  "scripts/",
  "SECURITY.md",
  "tests/",
  "version.py"
 ],
 "root .claude-plugin": [
  "marketplace.json"
 ],
 "marketplace": {
  "name": "dazzle-claude-plugins",
  "plugins": [
   [
    "bookmarks",
    "./plugin"
   ],
   [
    "session-logger",
    {
     "source": "url",
     "url": "https://github.com/DazzleML/claude-session-logger.git"
    }
   ],
   [
    "session-backup",
    {
     "source": "url",
     "url": "https://github.com/DazzleML/Claude-Session-Backup.git"
    }
   ]
  ],
  "version": "0.1.0"
 },
 "plugins": [
  {
   "folder": "plugin",
   "plugin.json keys": [
    "author",
    "description",
    "displayName",
    "documentationUrl",
    "homepage",
    "keywords",
    "license",
    "name",
    "privacyPolicyUrl",
    "repository",
    "supportUrl",
    "termsOfServiceUrl",
    "types",
    "userConfig",
    "version"
   ],
   "version": "0.6.8",
   "listing": [
    ".claude-plugin/",
    "hooks/",
    "images/",
    "LICENSE",
    "README.md",
    "templates/",
    "tests/",
    "tsconfig.json",
    "types/"
   ],
   "hooks": [
    "core/",
    "engine/",
    "handlers/",
    "hooks.json",
    "README.md",
    "register.tsx",
    "scripts/",
    "views/"
   ],
   "tsconfig": true,
   "package.json": false,
   "tests": [
    "after-action.test.ts",
    "band.test.ts",
    "check.test.ts",
    "debug.test.ts",
    "deletion.test.ts",
    "delmarks.test.ts"
   ],
   "README": true
  }
 ],
 "version-source": "version-source = \"version.py\"",
 "extra-targets": [
  "path = \"plugin/.claude-plugin/plugin.json\""
 ],
 "tag-format": "tag-format = \"human\"",
 "repokit-common vendored": true,
 "root tests": [
  "checklists/",
  "conftest.py",
  "core/",
  "mutation/",
  "one-offs/",
  "output/"
 ],
 "root README": true
}
```

## Claude-Session-Backup

```json
{
 "repo": "Claude-Session-Backup",
 "root": [
  ".claude/",
  ".claude-plugin/",
  ".ghtraf.json",
  ".github/",
  ".gitignore",
  ".repokit.json",
  "CHANGELOG.md",
  "CLAUDE.md",
  "claude_session_backup/",
  "claude_session_backup.egg-info/",
  "commands/",
  "CONTRIBUTING.md",
  "docs/",
  "hooks/",
  "install.py",
  "LICENSE",
  "pyproject.toml",
  "README.md",
  "requirements.txt",
  "scripts/",
  "tests/"
 ],
 "root .claude-plugin": [
  "marketplace.json",
  "plugin.json"
 ],
 "marketplace": {
  "name": "dazzle-claude-session-backup",
  "plugins": [
   [
    "claude-session-backup",
    "./"
   ]
  ],
  "version": null
 },
 "plugins": [
  {
   "folder": ".",
   "plugin.json keys": [
    "author",
    "description",
    "keywords",
    "license",
    "name",
    "repository",
    "version"
   ],
   "version": "0.10.1",
   "hooks": [
    "hooks.json",
    "scripts/"
   ],
   "tsconfig": false,
   "package.json": false,
   "tests": [
    "checklists/",
    "conftest.py",
    "fixtures/",
    "mutation/",
    "one-offs/",
    "output/"
   ],
   "README": true
  }
 ],
 "version-source": "version-source = \"claude_session_backup/_version.py\"",
 "extra-targets": [],
 "tag-format": "tag-format = \"pep440\"",
 "repokit-common vendored": true,
 "root tests": [
  "checklists/",
  "conftest.py",
  "fixtures/",
  "mutation/",
  "one-offs/",
  "output/"
 ],
 "root README": true
}
```

## claude-session-logger

```json
{
 "repo": "claude-session-logger",
 "root": [
  ".claude/",
  "github/",
  "local/",
  "test-hook-file.txt"
 ],
 "root .claude-plugin": [],
 "plugins": [
  {
   "folder": "github",
   "plugin.json keys": [
    "author",
    "commands",
    "description",
    "keywords",
    "license",
    "name",
    "repository",
    "version"
   ],
   "version": "0.3.19",
   "listing": [
    ".claude/",
    ".claude-plugin/",
    ".github/",
    ".gitignore",
    ".repokit.json",
    "CHANGELOG.md",
    "CLAUDE.md",
    "commands/",
    "CONTRIBUTING.md",
    "docs/",
    "examples/",
    "hooks/",
    "install.py",
    "LICENSE",
    "pyproject.toml",
    "README.md",
    "requirements.txt",
    "scripts-repo/",
    "settings.json.example",
    "tests/",
    "version.py"
   ],
   "hooks": [
    "hooks.json",
    "schemas/",
    "scripts/"
   ],
   "tsconfig": false,
   "package.json": false,
   "tests": [
    "checklists/",
    "mutation/",
    "one-offs/",
    "snapshots/"
   ],
   "README": true
  }
 ],
 "version-source": "",
 "extra-targets": [],
 "tag-format": "",
 "repokit-common vendored": false,
 "root tests": [],
 "root README": false
}
```

## dazzle-claude-plugins

```json
{
 "repo": "dazzle-claude-plugins",
 "root": [
  ".claude-plugin/",
  ".gitattributes",
  ".github/",
  ".gitignore",
  ".repokit.json",
  "CHANGELOG.md",
  "CONTRIBUTING.md",
  "LICENSE",
  "README.md",
  "tests/"
 ],
 "root .claude-plugin": [
  "marketplace.json"
 ],
 "marketplace": {
  "name": "dazzle-claude-plugins",
  "plugins": [
   [
    "session-logger",
    {
     "source": "url",
     "url": "https://github.com/DazzleML/claude-session-logger.git"
    }
   ],
   [
    "session-backup",
    {
     "source": "url",
     "url": "https://github.com/DazzleML/Claude-Session-Backup.git"
    }
   ],
   [
    "bookmarks",
    {
     "source": "git-subdir",
     "url": "https://github.com/DazzleML/claude-bookmarks.git",
     "path": "plugin"
    }
   ]
  ],
  "version": "0.1.1"
 },
 "plugins": [],
 "version-source": "",
 "extra-targets": [],
 "tag-format": "",
 "repokit-common vendored": false,
 "root tests": [
  "check_marketplace.py",
  "one-offs/"
 ],
 "root README": true
}
```
