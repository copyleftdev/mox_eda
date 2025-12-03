#!/usr/bin/env python3
"""
import_issues.py - Import RFC JSON schemas as GitHub Issues

Usage:
    python scripts/import_issues.py [--dry-run] [--epics-only] [--tasks-only]

Prerequisites:
    - gh CLI installed and authenticated
    - Python 3.8+
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
import argparse

REPO = "copyleftdev/mox_eda"
SCHEMA_DIR = Path(__file__).parent.parent / "docs" / "rfcs" / "schema"

# ANSI Colors
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def log_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")

def log_success(msg: str):
    print(f"{Colors.GREEN}[OK]{Colors.NC} {msg}")

def log_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")

def run_gh(args: list, check: bool = True) -> subprocess.CompletedProcess:
    """Run a gh CLI command."""
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        log_error(f"gh command failed: {' '.join(args)}")
        log_error(result.stderr)
    return result

def check_prerequisites():
    """Verify gh CLI is installed and authenticated."""
    result = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if result.returncode != 0:
        log_error("gh CLI not authenticated. Run: gh auth login")
        sys.exit(1)
    log_success("Prerequisites check passed")

def load_rfc(rfc_file: Path) -> dict:
    """Load an RFC JSON file."""
    with open(rfc_file) as f:
        return json.load(f)

def create_label(name: str, color: str, description: str = "", dry_run: bool = False):
    """Create a label if it doesn't exist."""
    if dry_run:
        return
    run_gh([
        "label", "create", name,
        "--color", color,
        "--description", description,
        "--repo", REPO,
        "--force"
    ], check=False)

def create_labels(dry_run: bool = False):
    """Create all labels."""
    log_info("Creating labels...")
    
    # Size labels
    sizes = [
        ("size:xs", "0E8A16", "Extra small (< 1 day)"),
        ("size:s", "1D76DB", "Small (1-2 days)"),
        ("size:m", "5319E7", "Medium (3-5 days)"),
        ("size:l", "D93F0B", "Large (1-2 weeks)"),
        ("size:xl", "B60205", "Extra large (2+ weeks)"),
    ]
    for name, color, desc in sizes:
        create_label(name, color, desc, dry_run)
    
    # Priority labels
    priorities = [
        ("priority:must", "B60205", "Must have"),
        ("priority:should", "FBCA04", "Should have"),
        ("priority:could", "0E8A16", "Could have"),
    ]
    for name, color, desc in priorities:
        create_label(name, color, desc, dry_run)
    
    # Epic label
    create_label("epic", "3E4B9E", "RFC Epic", dry_run)
    
    # Load category labels from index
    index_file = SCHEMA_DIR / "index.json"
    with open(index_file) as f:
        index = json.load(f)
    
    for label in index.get("labels", []):
        create_label(label, "C5DEF5", "", dry_run)
    
    log_success("Labels created")

def create_milestone(title: str, description: str, dry_run: bool = False) -> Optional[int]:
    """Create a milestone and return its number."""
    if dry_run:
        log_info(f"[DRY-RUN] Would create milestone: {title}")
        return None
    
    result = run_gh([
        "api", f"repos/{REPO}/milestones",
        "-f", f"title={title}",
        "-f", "state=open",
        "-f", f"description={description[:200]}..."
    ], check=False)
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return data.get("number")
    return None

def get_milestone_number(title: str) -> Optional[int]:
    """Get milestone number by title."""
    result = run_gh([
        "api", f"repos/{REPO}/milestones",
        "--jq", f'.[] | select(.title == "{title}") | .number'
    ], check=False)
    if result.returncode == 0 and result.stdout.strip():
        return int(result.stdout.strip())
    return None

def create_issue(
    title: str,
    body: str,
    labels: list[str],
    milestone: Optional[int] = None,
    dry_run: bool = False
) -> bool:
    """Create a GitHub issue."""
    if dry_run:
        log_info(f"[DRY-RUN] Would create issue: {title}")
        print(f"  Labels: {', '.join(labels)}")
        return True
    
    args = [
        "issue", "create",
        "--repo", REPO,
        "--title", title,
        "--body", body,
    ]
    
    for label in labels:
        args.extend(["--label", label])
    
    if milestone:
        args.extend(["--milestone", str(milestone)])
    
    result = run_gh(args, check=False)
    return result.returncode == 0

def create_epic_issue(rfc: dict, dry_run: bool = False) -> bool:
    """Create an epic issue for an RFC."""
    rfc_id = rfc["id"]
    rfc_title = rfc["title"]
    
    title = f"[EPIC] {rfc_id}: {rfc_title}"
    
    # Build body
    body = f"""# {rfc_id}: {rfc_title}

## Summary

{rfc.get('summary', '')}

## Motivation

{rfc.get('motivation', '')}

## Scope

- **Tasks:** {len(rfc.get('tasks', []))}
- **Acceptance Criteria:** {len(rfc.get('acceptance_criteria', []))}

## Tasks

"""
    
    for task in rfc.get("tasks", []):
        body += f"- [ ] {task['id']}: {task['title']}\n"
    
    body += "\n## Acceptance Criteria\n\n"
    
    for ac in rfc.get("acceptance_criteria", []):
        priority = ac.get("priority", "should")
        body += f"- [ ] **{ac['id']}** [{priority}]: {ac['criterion']}\n"
    
    body += "\n## References\n\n"
    
    for ref in rfc.get("references", []):
        body += f"- [{ref['title']}]({ref['url']})\n"
    
    success = create_issue(title, body, ["epic"], dry_run=dry_run)
    if success:
        log_success(f"Created epic: {title}")
    else:
        log_error(f"Failed to create epic: {title}")
    
    return success

def create_task_issue(
    rfc: dict,
    task: dict,
    milestone_num: Optional[int],
    dry_run: bool = False
) -> bool:
    """Create an issue for a task."""
    rfc_id = rfc["id"]
    rfc_title = rfc["title"]
    task_id = task["id"]
    
    title = f"[{rfc_id}] {task['title']}"
    
    # Build body
    body = f"""## {task_id}: {task['title']}

**RFC:** {rfc_id} - {rfc_title}
**Component:** {task.get('component', 'N/A')}
**Estimate:** {task.get('estimate', 'N/A')}

## Description

{task.get('description', '')}

## Acceptance Criteria

"""
    
    # Find matching acceptance criteria
    ac_ids = task.get("acceptance_criteria_ids", [])
    all_acs = {ac["id"]: ac for ac in rfc.get("acceptance_criteria", [])}
    
    for ac_id in ac_ids:
        if ac_id in all_acs:
            ac = all_acs[ac_id]
            body += f"- [ ] **{ac_id}**: {ac['criterion']}\n"
            body += f"  - Verification: {ac.get('verification', 'N/A')}\n"
    
    # Dependencies
    depends = task.get("depends_on", [])
    if depends:
        body += f"\n## Dependencies\n\nDepends on: {', '.join(depends)}\n"
    
    # Build labels
    labels = list(task.get("labels", []))
    estimate = task.get("estimate", "m")
    labels.append(f"size:{estimate}")
    
    success = create_issue(title, body, labels, milestone_num, dry_run)
    if success:
        log_success(f"Created: {title}")
    else:
        log_error(f"Failed: {title}")
    
    return success

def import_all(dry_run: bool = False, epics_only: bool = False, tasks_only: bool = False):
    """Import all RFCs as GitHub issues."""
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║       RFC to GitHub Issues Importer                       ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    
    if dry_run:
        log_warn("DRY RUN MODE - No changes will be made")
        print()
    
    check_prerequisites()
    
    # Load all RFCs
    rfc_files = sorted(SCHEMA_DIR.glob("RFC-*.json"))
    log_info(f"Found {len(rfc_files)} RFC files")
    
    # Count totals
    total_tasks = 0
    for rf in rfc_files:
        rfc = load_rfc(rf)
        total_tasks += len(rfc.get("tasks", []))
    
    log_info(f"Total tasks to create: {total_tasks}")
    log_info(f"Total epics to create: {len(rfc_files)}")
    print()
    
    if not dry_run:
        response = input(f"This will create ~{total_tasks + len(rfc_files)} issues. Continue? (y/N) ")
        if response.lower() != 'y':
            log_info("Aborted")
            return
    
    # Create labels
    create_labels(dry_run)
    
    # Process each RFC
    for rfc_file in rfc_files:
        rfc = load_rfc(rfc_file)
        rfc_id = rfc["id"]
        rfc_title = rfc["title"]
        
        log_info(f"Processing {rfc_id}: {rfc_title}")
        
        # Create milestone
        milestone_title = f"{rfc_id}: {rfc_title}"
        milestone_num = None
        
        if not dry_run:
            create_milestone(milestone_title, rfc.get("summary", ""), dry_run)
            milestone_num = get_milestone_number(milestone_title)
        
        # Create epic
        if not tasks_only:
            create_epic_issue(rfc, dry_run)
            if not dry_run:
                time.sleep(1)  # Rate limit
        
        # Create task issues
        if not epics_only:
            for task in rfc.get("tasks", []):
                create_task_issue(rfc, task, milestone_num, dry_run)
                if not dry_run:
                    time.sleep(1)  # Rate limit
    
    print()
    log_success("Import complete!")
    print()
    print(f"View issues at: https://github.com/{REPO}/issues")
    print()

def main():
    parser = argparse.ArgumentParser(description="Import RFC schemas as GitHub Issues")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating issues")
    parser.add_argument("--epics-only", action="store_true", help="Only create epic issues")
    parser.add_argument("--tasks-only", action="store_true", help="Only create task issues")
    
    args = parser.parse_args()
    
    import_all(
        dry_run=args.dry_run,
        epics_only=args.epics_only,
        tasks_only=args.tasks_only
    )

if __name__ == "__main__":
    main()
