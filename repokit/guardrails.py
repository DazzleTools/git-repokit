#!/usr/bin/env python3
"""
RepoKit Guardrails - Protection against private content leakage.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

from .branch_utils import BranchContext
from .utils import logger


class GuardrailsManager:
    """Manages RepoKit guardrails for private content protection."""
    
    def __init__(self, repo_path: str = '.'):
        """Initialize guardrails manager."""
        self.repo_path = Path(repo_path).resolve()
        self.git_dir = self.repo_path / '.git'
        self.hooks_dir = self.git_dir / 'hooks'
        self.context = BranchContext(str(self.repo_path))
    
    def setup_guardrails(self, force: bool = False) -> bool:
        """
        Set up all guardrails for the repository.
        
        Args:
            force: Overwrite existing hooks if True
            
        Returns:
            True if successful, False otherwise
        """
        logger.info("Setting up RepoKit guardrails...")
        
        # Ensure we're in a git repository
        if not self.git_dir.exists():
            logger.error("Not in a git repository!")
            return False
        
        # Create hooks directory if needed
        self.hooks_dir.mkdir(exist_ok=True)
        
        # Set up pre-commit hook
        if not self._install_hook('pre-commit', force):
            return False
        
        # Set up branch excludes
        self.context.setup_branch_excludes()
        
        # Set up post-checkout hook for automatic exclude updates
        if not self._install_hook('post-checkout', force):
            return False
        
        logger.info("✅ RepoKit guardrails successfully installed!")
        self._print_status()
        
        return True
    
    def _vendored_common(self) -> Optional[Path]:
        """The project's git-repokit-common copy (the folder with install-hooks.sh), if any."""
        for candidate in (self.repo_path / "scripts" / "repokit-common", self.repo_path / "scripts"):
            if (candidate / "install-hooks.sh").is_file() and (candidate / "repokit_config.py").is_file():
                return candidate
        return None

    def setup_repokit_common(self, vendor: bool = False) -> int:
        """Install git-repokit-common's hooks, with the private-branch settings.

        Never vendors silently: adding the subtree makes commits, so it needs
        --vendor and a clean working tree. Returns a process exit code.
        """
        from . import common_kit
        from .defaults import DEFAULT_PRIVATE_DIRS, DEFAULT_SENSITIVE_FILES

        if not self.git_dir.exists():
            logger.error("Not in a git repository!")
            return 1

        copy = self._vendored_common()
        if copy is None:
            src = common_kit.source({})
            url, ref = src if src else (common_kit.DEFAULT_URL, common_kit.DEFAULT_REF)
            if not vendor:
                print("This project has no git-repokit-common copy, whose hooks the guardrails use.")
                print("Add it (two commits on the current branch), then re-run:")
                print(f"  git subtree add --prefix={common_kit.PREFIX} {url} {ref} --squash")
                print("or run: repokit setup-guardrails --vendor")
                print("(repokit setup-guardrails --legacy installs git-repokit's previous hooks instead.)")
                return 1
            dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                   cwd=self.repo_path, capture_output=True, text=True).stdout.strip()
            if dirty:
                print("The working tree has uncommitted changes; commit or stash them before --vendor.")
                return 1
            problem = common_kit.vendor(str(self.repo_path), url, ref)
            if problem:
                print(f"Could not add git-repokit-common: {problem}")
                return 1
            print(f"Added git-repokit-common at {common_kit.PREFIX}/")
            print(common_kit.RESIGN_HINT)
            copy = self._vendored_common()

        private_paths = ["CLAUDE.md"] + [f"{d.rstrip('/')}/" for d in DEFAULT_PRIVATE_DIRS] + list(DEFAULT_SENSITIVE_FILES)
        private_branch = self.context.current_branch if self.context.is_private_branch() else None
        written = common_kit.write_settings(
            str(self.repo_path), common_kit.private_branch_settings(private_branch, private_paths))
        if written:
            print(f"Wrote the private-branch settings to {written} -- commit it on every branch that should be checked.")

        # install-hooks.sh asks before replacing a pre-commit that is not one
        # of its stubs, and cannot be answered from here. Running this command
        # is the request to switch, so move the old hooks aside -- renamed,
        # never deleted -- and let it install into a free slot.
        for name, suffix, mine in (
            ("pre-commit", ".before-repokit-common", lambda t: "repokit-common hook stub" not in t),
            ("post-checkout", ".disabled", lambda t: "RepoKit" in t and "post-checkout" in t.lower()),
        ):
            hook = self.hooks_dir / name
            if hook.is_file() and mine(hook.read_text(encoding="utf-8", errors="replace")):
                target = self.hooks_dir / (name + suffix)
                n = 1
                while target.exists():
                    n += 1
                    target = self.hooks_dir / f"{name}{suffix}.{n}"
                hook.rename(target)
                print(f"Moved the previous {name} hook to {target.name}")

        problem = common_kit.install_hooks(str(self.repo_path))
        if problem:
            print(f"Could not install the hooks: {problem}")
            return 1

        # Branch-specific exclusions (a setup step, not a hook) stay git-repokit's
        self.context.setup_branch_excludes()

        print("git-repokit-common hooks installed (pre-commit, post-commit, pre-push).")
        self._print_status()
        return 0

    def _install_hook(self, hook_name: str, force: bool = False) -> bool:
        """Install a specific git hook."""
        hook_path = self.hooks_dir / hook_name
        
        # Check if hook already exists
        if hook_path.exists() and not force:
            logger.warning(f"Hook {hook_name} already exists. Use --force to overwrite.")
            return True
        
        # Get hook content based on type
        if hook_name == 'pre-commit':
            hook_content = self._get_pre_commit_hook()
        elif hook_name == 'post-checkout':
            hook_content = self._get_post_checkout_hook()
        else:
            logger.error(f"Unknown hook type: {hook_name}")
            return False
        
        # Write hook file
        try:
            # Hook templates are UTF-8; Windows' default codec cannot write them
            hook_path.write_text(hook_content, encoding='utf-8')
            # Make executable
            hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
            logger.info(f"✓ Installed {hook_name} hook")
            return True
        except Exception as e:
            logger.error(f"Failed to install {hook_name} hook: {e}")
            return False
    
    def _get_pre_commit_hook(self) -> str:
        """Get pre-commit hook content."""
        # Try to use the template we created
        template_path = Path(__file__).parent / 'hooks' / 'pre-commit-guardrails'
        if template_path.exists():
            return template_path.read_text(encoding='utf-8')
        
        # Fallback to inline version
        return '''#!/usr/bin/env python3
"""RepoKit pre-commit hook for private content protection."""

import sys
import os

# Try to use installed repokit
try:
    from repokit.branch_utils import BranchContext
    
    context = BranchContext()
    print(f"🔍 RepoKit Pre-Commit Check")
    print(f"   Branch: {context.current_branch} ({context.branch_type})")
    
    is_valid, errors = context.validate_commit()
    
    if not is_valid:
        print("\\n❌ COMMIT BLOCKED - Private Content Protection\\n")
        for error in errors:
            print(error)
        sys.exit(1)
    
    print("\\n✅ Pre-commit checks passed!")
    sys.exit(0)
    
except ImportError:
    # RepoKit not installed, basic check
    import subprocess
    
    result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                          capture_output=True, text=True)
    branch = result.stdout.strip()
    
    if branch not in ['private', 'local']:
        # Check for obvious private files
        result = subprocess.run(['git', 'diff', '--cached', '--name-only'],
                              capture_output=True, text=True)
        files = result.stdout.strip().split('\\n')
        
        private_files = [f for f in files if 'CLAUDE.md' in f or 'private/' in f]
        
        if private_files:
            print(f"\\n❌ ERROR: Attempting to commit private files to branch '{branch}':")
            for f in private_files:
                print(f"  - {f}")
            print("\\nThese files should only exist in private branches!")
            sys.exit(1)
    
    sys.exit(0)
'''
    
    def _get_post_checkout_hook(self) -> str:
        """Get post-checkout hook content."""
        return '''#!/bin/sh
# RepoKit Cross-Environment Post-Checkout Hook
# This wrapper script detects the environment and calls Python appropriately

# Function to detect Python command
find_python() {
    # Try to detect if we're on Windows
    if [ -n "$WINDIR" ] || [ "$OSTYPE" = "msys" ] || [ "$OSTYPE" = "cygwin" ]; then
        # Windows environment - try various Python commands
        if command -v py >/dev/null 2>&1; then
            echo "py"
        elif command -v python >/dev/null 2>&1; then
            echo "python"
        elif command -v python3 >/dev/null 2>&1; then
            echo "python3"
        else
            echo ""
        fi
    else
        # Unix/Linux/WSL environment
        if command -v python3 >/dev/null 2>&1; then
            echo "python3"
        elif command -v python >/dev/null 2>&1; then
            echo "python"
        else
            echo ""
        fi
    fi
}

# Find Python command
PYTHON_CMD=$(find_python)

# If Python not found, exit gracefully
if [ -z "$PYTHON_CMD" ]; then
    echo "⚠️  Python not found - skipping RepoKit post-checkout tasks"
    echo "   To enable: Install Python and ensure it's in PATH"
    exit 0
fi

# Execute the Python script with all arguments (UTF-8 output: its messages
# contain emoji, which a non-UTF-8 console cannot encode)
PYTHONIOENCODING=utf-8 $PYTHON_CMD - "$@" << 'EOF'
"""RepoKit post-checkout hook to update excludes and restore private files."""

import sys
import os
import subprocess
import shutil
from pathlib import Path

try:
    from repokit.branch_utils import BranchContext
    
    # Get the new branch (third argument)
    if len(sys.argv) > 3:
        # Full checkout (not file checkout)
        if sys.argv[3] == '1':
            context = BranchContext()
            print(f"\\n🔄 Switched to branch: {context.current_branch}")
            
            # Update branch excludes
            context.setup_branch_excludes()
            
            # Handle private file restoration
            if context.is_public_branch():
                # Restore private files from private branch
                print("📄 Restoring private files for AI assistance...")
                
                # Files to restore
                private_files = [
                    'CLAUDE.md',
                    'private/claude/',
                    'private/docs/',
                ]
                
                try:
                    # Get the current commit of private branch
                    result = subprocess.run(
                        ['git', 'rev-parse', 'private'],
                        capture_output=True, text=True
                    )
                    private_commit = result.stdout.strip()
                    
                    if result.returncode == 0:
                        # Restore each private file/directory
                        for file_path in private_files:
                            try:
                                if file_path.endswith('/'):
                                    # Directory - use git archive
                                    archive_cmd = [
                                        'git', 'archive', private_commit,
                                        '--format=tar', file_path
                                    ]
                                    extract_cmd = ['tar', '-xf', '-']
                                    
                                    archive = subprocess.Popen(
                                        archive_cmd, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=False
                                    )
                                    subprocess.run(
                                        extract_cmd, stdin=archive.stdout,
                                        check=True, stderr=subprocess.PIPE
                                    )
                                    archive.wait()
                                else:
                                    # Single file - use git show
                                    result = subprocess.run(
                                        ['git', 'show', f'{private_commit}:{file_path}'],
                                        capture_output=True, text=True
                                    )
                                    if result.returncode == 0:
                                        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                                        Path(file_path).write_text(result.stdout)
                                        
                            except subprocess.CalledProcessError:
                                # File might not exist in private branch
                                pass
                        
                        # Update .gitignore to ensure private files are ignored
                        gitignore = Path('.gitignore')
                        if gitignore.exists():
                            content = gitignore.read_text()
                            
                            # Add private patterns if not present
                            private_patterns = [
                                '\\n# RepoKit Private Content (DO NOT REMOVE)',
                                'CLAUDE.md',
                                'private/claude/',
                                'private/docs/',
                                'private/notes/',
                                'private/temp/',
                            ]
                            
                            needs_update = False
                            for pattern in private_patterns[1:]:  # Skip comment
                                if pattern not in content:
                                    needs_update = True
                                    break
                            
                            if needs_update:
                                # Add private section at the end
                                if not content.endswith('\\n'):
                                    content += '\\n'
                                content += '\\n'.join(private_patterns) + '\\n'
                                gitignore.write_text(content)
                                print("✓ Updated .gitignore with private patterns")
                        
                        print("✓ Private files restored for AI assistance")
                        print("  Note: These files are ignored and won't be committed")
                        
                except Exception as e:
                    print(f"⚠️  Could not restore private files: {e}")
                    print("  Run 'repokit restore-private' to restore manually")
            
            elif context.is_private_branch():
                # In private branch - ensure .gitignore doesn't exclude private files
                gitignore = Path('.gitignore')
                if gitignore.exists():
                    content = gitignore.read_text()
                    lines = content.split('\\n')
                    
                    # Remove private file exclusions
                    private_patterns = ['CLAUDE.md', 'private/claude/', 'private/docs/', 'private/notes/', 'private/temp/']
                    filtered_lines = []
                    skip_next = False
                    
                    for line in lines:
                        if '# RepoKit Private Content' in line:
                            skip_next = True
                            continue
                        if skip_next and line.strip() in private_patterns:
                            continue
                        if skip_next and line.strip() == '':
                            skip_next = False
                            continue
                        filtered_lines.append(line)
                    
                    new_content = '\\n'.join(filtered_lines)
                    if new_content != content:
                        gitignore.write_text(new_content)
                        print("✓ Updated .gitignore for private branch")
    
except ImportError:
    # RepoKit not installed, skip
    pass

sys.exit(0)
EOF
'''
    
    def check_status(self) -> Dict[str, any]:
        """Check current guardrails status."""
        status = {
            'branch': self.context.current_branch,
            'branch_type': self.context.branch_type,
            'pre_commit_hook': (self.hooks_dir / 'pre-commit').exists(),
            'repokit_common_hooks': (self.hooks_dir / 'pre-commit').is_file() and
                'repokit-common hook stub' in (self.hooks_dir / 'pre-commit').read_text(encoding='utf-8', errors='replace'),
            'post_checkout_hook': (self.hooks_dir / 'post-checkout').exists(),
            'excludes_configured': (self.git_dir / 'info' / 'exclude').exists(),
            'staged_files': self.context.get_staged_files(),
            'private_files_staged': [],
        }
        
        # Check for private files in staging
        if status['staged_files']:
            private_files = self.context.check_private_files(status['staged_files'])
            status['private_files_staged'] = private_files
        
        return status
    
    def _print_status(self) -> None:
        """Print current guardrails status."""
        status = self.check_status()
        
        print("\n📊 RepoKit Guardrails Status:")
        print(f"   Current Branch: {status['branch']} ({status['branch_type']})")
        print(f"   Pre-commit Hook: {'✅' if status['pre_commit_hook'] else '❌'}"
              f"{' (git-repokit-common)' if status['repokit_common_hooks'] else ''}")
        print(f"   Post-checkout Hook: {'✅' if status['post_checkout_hook'] else '❌'}")
        print(f"   Branch Excludes: {'✅' if status['excludes_configured'] else '❌'}")
        
        if status['private_files_staged'] and status['branch_type'] == 'public':
            print("\n⚠️  WARNING: Private files staged in public branch:")
            for file, reason in status['private_files_staged']:
                print(f"   - {file}: {reason}")
    
    def validate_merge(self, source_branch: str, target_branch: Optional[str] = None) -> bool:
        """
        Validate if merge is safe regarding private content.
        
        Args:
            source_branch: Branch to merge from
            target_branch: Branch to merge to (current if None)
            
        Returns:
            True if merge is safe, False otherwise
        """
        if target_branch is None:
            target_branch = self.context.current_branch
        
        # Get excludes for this merge
        excludes = self.context.get_merge_excludes(source_branch, target_branch)
        
        if excludes:
            logger.warning(f"⚠️  Merging from '{source_branch}' to '{target_branch}'")
            logger.warning("The following files will be excluded:")
            for exclude in sorted(excludes):
                logger.warning(f"  - {exclude}")
            
            return True
        
        return True
    
    def safe_merge(self, source_branch: str, no_commit: bool = True, 
                   no_ff: bool = True, preview: bool = False) -> bool:
        """
        Perform a safe merge that respects private content rules.
        
        Args:
            source_branch: Branch to merge from
            no_commit: Use --no-commit flag
            no_ff: Use --no-ff flag
            preview: Only show what would be merged
            
        Returns:
            True if successful, False otherwise
        """
        target_branch = self.context.current_branch
        
        # Validate merge
        if not self.validate_merge(source_branch, target_branch):
            return False
        
        # Get files to exclude
        excludes = self.context.get_merge_excludes(source_branch, target_branch)
        
        if preview:
            print(f"\n🔍 Preview: Merge '{source_branch}' → '{target_branch}'")
            
            # Show commits that would be merged
            result = subprocess.run(
                ['git', 'log', '--oneline', f'{target_branch}..{source_branch}'],
                capture_output=True, text=True
            )
            print("\nCommits to merge:")
            print(result.stdout)
            
            if excludes:
                print("\nFiles that will be excluded:")
                for exclude in sorted(excludes):
                    print(f"  - {exclude}")
            
            return True
        
        # Perform merge
        merge_args = ['git', 'merge', source_branch]
        if no_ff:
            merge_args.append('--no-ff')
        if no_commit:
            merge_args.append('--no-commit')
        
        logger.info(f"Merging '{source_branch}' → '{target_branch}'...")
        result = subprocess.run(merge_args, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Merge failed: {result.stderr}")
            return False
        
        # If we have excludes and merge succeeded, remove excluded files
        if excludes and no_commit:
            logger.info("Removing excluded files from merge...")
            for exclude in excludes:
                try:
                    subprocess.run(['git', 'rm', '-rf', '--ignore-unmatch', exclude], 
                                 check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError:
                    pass  # File might not exist
            
            print("\n✅ Safe merge completed. Excluded files have been removed.")
            print("Review changes and commit when ready.")
        
        return True


def setup_guardrails_command(args) -> int:
    """CLI command to set up guardrails.

    By default the hooks are git-repokit-common's (djdarcy, 2026-10-08: "we
    should switch it to repokit-common hooks as all future projects should be
    using all of our tools properly"). --legacy keeps git-repokit's previous
    hooks available.
    """
    manager = GuardrailsManager()

    if getattr(args, "legacy", False):
        return 0 if manager.setup_guardrails(force=args.force) else 1
    return manager.setup_repokit_common(vendor=getattr(args, "vendor", False))


def check_guardrails_command(args) -> int:
    """CLI command to check guardrails status."""
    manager = GuardrailsManager()
    manager._print_status()
    
    # Run validation
    context = BranchContext()
    is_valid, errors = context.validate_commit()
    
    if not is_valid:
        print("\n❌ Current state would fail pre-commit check!")
        return 1
    
    print("\n✅ Current state passes all checks!")
    return 0


def restore_private_files() -> bool:
    """Restore private files from private branch to current branch."""
    try:
        # Get current branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True
        )
        current_branch = result.stdout.strip()
        
        if current_branch == 'private':
            print("Already on private branch - files should be present.")
            return True
        
        print(f"Restoring private files to '{current_branch}' branch...")
        
        # Get private branch commit
        result = subprocess.run(
            ['git', 'rev-parse', 'private'],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print("❌ Private branch not found!")
            return False
        
        private_commit = result.stdout.strip()
        
        # Files to restore
        files_to_restore = [
            ('CLAUDE.md', False),
            ('private/claude/', True),
            ('private/docs/', True),
        ]
        
        restored_count = 0
        for file_path, is_dir in files_to_restore:
            try:
                if is_dir:
                    # Use git archive for directories
                    print(f"  Restoring {file_path}...")
                    archive_cmd = ['git', 'archive', private_commit, '--format=tar', file_path]
                    extract_cmd = ['tar', '-xf', '-']
                    
                    archive = subprocess.Popen(archive_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
                    extract = subprocess.run(extract_cmd, stdin=archive.stdout, capture_output=True, text=False)
                    archive.wait()
                    
                    if archive.returncode == 0:
                        restored_count += 1
                else:
                    # Use git show for single files
                    result = subprocess.run(
                        ['git', 'show', f'{private_commit}:{file_path}'],
                        capture_output=True, text=True
                    )
                    
                    if result.returncode == 0:
                        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                        Path(file_path).write_text(result.stdout)
                        print(f"  Restored {file_path}")
                        restored_count += 1
                        
            except Exception as e:
                print(f"  ⚠️  Could not restore {file_path}: {e}")
        
        print(f"\n✅ Restored {restored_count} private file(s)/folder(s)")
        print("Note: These files are ignored by git and won't be committed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error restoring private files: {e}")
        return False


def sync_private_files() -> bool:
    """Sync private file changes back to private branch."""
    try:
        context = BranchContext()
        
        if context.is_private_branch():
            print("Already on private branch - use git add/commit directly.")
            return True
        
        print("Syncing private file changes to private branch...")
        
        # Stash current changes
        print("1. Stashing current changes...")
        subprocess.run(['git', 'stash', 'push', '-m', 'repokit-sync-private'], check=True, capture_output=True, text=True)
        
        # Switch to private branch
        print("2. Switching to private branch...")
        subprocess.run(['git', 'checkout', 'private'], check=True, capture_output=True, text=True)
        
        # Apply stash
        print("3. Applying changes...")
        result = subprocess.run(['git', 'stash', 'pop'], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("⚠️  Some conflicts occurred. Please resolve manually.")
            return False
        
        print("\n✅ Changes synced to private branch")
        print("Next steps:")
        print("  1. Review changes: git status")
        print("  2. Add files: git add <files>")
        print("  3. Commit: git commit -m 'your message'")
        print("  4. Return to previous branch: git checkout -")
        
        return True
        
    except Exception as e:
        print(f"❌ Error syncing to private branch: {e}")
        return False