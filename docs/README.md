# git-repokit documentation

Start with the [main README](../README.md): what a project gets, installation, and the Quick Start. These guides go further.

## Making projects

1. **[Configuration](Configuration.md)**: every config key and the flag that matches it, and how to keep your house style in `~/.repokit/config.json`
2. **[Languages and layers](Languages-and-Layers.md)**: the presets for Python, C/C++ and JavaScript/TypeScript, `--with`, several languages, and adding a language
3. **[GitHub setup](GitHub-Setup.md)**: `--github`, the `--github-setup` steps, and what is still done by hand
4. **[The vault](The-Vault.md)**: `private/`, the files it starts with, and the sessions that use it
5. **[Recipes and how-tos](Recipes-And-Howtos.md)**: commands for common cases

## Existing projects

- **[Adoption guide](Adoption-Guide.md)**: adding repokit's structure to a project you already have, step by step
- **[Migration guide](Migration-Guide.md)**: the harder cases, from loose folders to repositories with history

## Branches and workflow

- **[Branch strategies](Branch-Strategies.md)**: main-only (the default) and the private-branch strategies
- **[Workflow guide](Workflow-Guide.md)**: day-to-day work under the private-branch strategies
- **[Deployment demo](Deployment-Demo.md)**: worked examples, from a new project to GitHub

## Credentials

- **[Auth guide](Auth-Guide.md)**: the `gh` login for `--github`, and tokens for `--publish-to`

## Platforms

- **[Platform support](platform-support.md)**: what runs where on Windows, Linux and macOS, and what each needs

## Background

- **[Why repokit exists](Why-RepoKit-Exists.md)**: the problem it solves

## Getting help

- `repokit --help`, and `repokit <command> --help` for each command's options and examples
- `repokit list` for the languages, presets and layers
- [Issues](https://github.com/DazzleTools/git-repokit/issues) and [Discussions](https://github.com/DazzleTools/git-repokit/discussions)
