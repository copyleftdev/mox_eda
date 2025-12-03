#!/bin/bash
# import-issues.sh - Import RFC tasks as GitHub Issues
#
# Usage: ./scripts/import-issues.sh [--dry-run]
#
# Prerequisites:
#   - gh CLI authenticated
#   - jq installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_DIR="${SCRIPT_DIR}/../docs/rfcs/schema"
REPO="copyleftdev/mox_eda"
DRY_RUN="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    if ! command -v gh &> /dev/null; then
        log_error "gh CLI not found. Install with: brew install gh"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Install with: brew install jq"
        exit 1
    fi
    
    if ! gh auth status &> /dev/null; then
        log_error "gh CLI not authenticated. Run: gh auth login"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Create labels if they don't exist
create_labels() {
    log_info "Creating labels..."
    
    # Size labels
    gh label create "size:xs" --color "0E8A16" --description "Extra small (< 1 day)" --repo "$REPO" 2>/dev/null || true
    gh label create "size:s" --color "1D76DB" --description "Small (1-2 days)" --repo "$REPO" 2>/dev/null || true
    gh label create "size:m" --color "5319E7" --description "Medium (3-5 days)" --repo "$REPO" 2>/dev/null || true
    gh label create "size:l" --color "D93F0B" --description "Large (1-2 weeks)" --repo "$REPO" 2>/dev/null || true
    gh label create "size:xl" --color "B60205" --description "Extra large (2+ weeks)" --repo "$REPO" 2>/dev/null || true
    
    # Priority labels
    gh label create "priority:must" --color "B60205" --description "Must have" --repo "$REPO" 2>/dev/null || true
    gh label create "priority:should" --color "FBCA04" --description "Should have" --repo "$REPO" 2>/dev/null || true
    gh label create "priority:could" --color "0E8A16" --description "Could have" --repo "$REPO" 2>/dev/null || true
    
    # Category labels from index.json
    local labels=$(jq -r '.labels[]' "${SCHEMA_DIR}/index.json")
    for label in $labels; do
        gh label create "$label" --color "C5DEF5" --repo "$REPO" 2>/dev/null || true
    done
    
    log_success "Labels created"
}

# Create milestones for each RFC
create_milestones() {
    log_info "Creating milestones..."
    
    for rfc_file in "${SCHEMA_DIR}"/RFC-*.json; do
        local rfc_id=$(jq -r '.id' "$rfc_file")
        local rfc_title=$(jq -r '.title' "$rfc_file")
        local milestone_title="${rfc_id}: ${rfc_title}"
        
        if [[ "$DRY_RUN" == "--dry-run" ]]; then
            log_info "[DRY-RUN] Would create milestone: $milestone_title"
        else
            gh api repos/${REPO}/milestones \
                -f title="$milestone_title" \
                -f state="open" \
                -f description="$(jq -r '.summary' "$rfc_file")" \
                2>/dev/null || log_warn "Milestone may already exist: $milestone_title"
        fi
    done
    
    log_success "Milestones created"
}

# Get milestone number by title
get_milestone_number() {
    local title="$1"
    gh api "repos/${REPO}/milestones" --jq ".[] | select(.title == \"$title\") | .number" 2>/dev/null || echo ""
}

# Create issues from tasks
create_issues() {
    log_info "Creating issues from RFC tasks..."
    
    local total_tasks=0
    local created_tasks=0
    
    for rfc_file in "${SCHEMA_DIR}"/RFC-*.json; do
        local rfc_id=$(jq -r '.id' "$rfc_file")
        local rfc_title=$(jq -r '.title' "$rfc_file")
        local milestone_title="${rfc_id}: ${rfc_title}"
        
        log_info "Processing ${rfc_id}..."
        
        # Get milestone number
        local milestone_num=""
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
            milestone_num=$(get_milestone_number "$milestone_title")
        fi
        
        # Get number of tasks
        local task_count=$(jq '.tasks | length' "$rfc_file")
        
        for i in $(seq 0 $((task_count - 1))); do
            local task_id=$(jq -r ".tasks[$i].id" "$rfc_file")
            local task_title=$(jq -r ".tasks[$i].title" "$rfc_file")
            local task_desc=$(jq -r ".tasks[$i].description" "$rfc_file")
            local task_component=$(jq -r ".tasks[$i].component" "$rfc_file")
            local task_estimate=$(jq -r ".tasks[$i].estimate" "$rfc_file")
            local task_labels=$(jq -r ".tasks[$i].labels | join(\",\")" "$rfc_file")
            local task_depends=$(jq -r ".tasks[$i].depends_on | join(\", \")" "$rfc_file")
            local ac_ids=$(jq -r ".tasks[$i].acceptance_criteria_ids | join(\", \")" "$rfc_file")
            
            # Build issue title
            local issue_title="[${rfc_id}] ${task_title}"
            
            # Build issue body
            local issue_body="## ${task_id}: ${task_title}

**RFC:** ${rfc_id} - ${rfc_title}
**Component:** ${task_component}
**Estimate:** ${task_estimate}

## Description

${task_desc}

## Acceptance Criteria

"
            # Add acceptance criteria as checklist
            for ac_id in $(jq -r ".tasks[$i].acceptance_criteria_ids[]" "$rfc_file" 2>/dev/null); do
                local ac_criterion=$(jq -r ".acceptance_criteria[] | select(.id == \"$ac_id\") | .criterion" "$rfc_file")
                local ac_verification=$(jq -r ".acceptance_criteria[] | select(.id == \"$ac_id\") | .verification" "$rfc_file")
                issue_body+="- [ ] **${ac_id}**: ${ac_criterion}
  - Verification: ${ac_verification}
"
            done
            
            # Add dependencies
            if [[ "$task_depends" != "" && "$task_depends" != "null" ]]; then
                issue_body+="
## Dependencies

Depends on: ${task_depends}
"
            fi
            
            # Build labels array
            local label_args=""
            IFS=',' read -ra LABEL_ARRAY <<< "$task_labels"
            for label in "${LABEL_ARRAY[@]}"; do
                label_args+=" --label \"${label}\""
            done
            label_args+=" --label \"size:${task_estimate}\""
            
            ((total_tasks++))
            
            if [[ "$DRY_RUN" == "--dry-run" ]]; then
                log_info "[DRY-RUN] Would create issue: $issue_title"
                echo "  Labels: $task_labels, size:$task_estimate"
                echo "  Component: $task_component"
            else
                # Create the issue
                local milestone_arg=""
                if [[ -n "$milestone_num" ]]; then
                    milestone_arg="--milestone $milestone_num"
                fi
                
                # Use gh issue create
                if gh issue create \
                    --repo "$REPO" \
                    --title "$issue_title" \
                    --body "$issue_body" \
                    --label "$task_labels" \
                    --label "size:$task_estimate" \
                    $milestone_arg 2>/dev/null; then
                    ((created_tasks++))
                    log_success "Created: $issue_title"
                else
                    log_error "Failed to create: $issue_title"
                fi
                
                # Rate limit protection
                sleep 1
            fi
        done
    done
    
    if [[ "$DRY_RUN" == "--dry-run" ]]; then
        log_info "[DRY-RUN] Would create $total_tasks issues"
    else
        log_success "Created $created_tasks / $total_tasks issues"
    fi
}

# Create parent epic issues for each RFC
create_epic_issues() {
    log_info "Creating RFC epic issues..."
    
    for rfc_file in "${SCHEMA_DIR}"/RFC-*.json; do
        local rfc_id=$(jq -r '.id' "$rfc_file")
        local rfc_title=$(jq -r '.title' "$rfc_file")
        local rfc_summary=$(jq -r '.summary' "$rfc_file")
        local rfc_motivation=$(jq -r '.motivation' "$rfc_file")
        local task_count=$(jq '.tasks | length' "$rfc_file")
        local ac_count=$(jq '.acceptance_criteria | length' "$rfc_file")
        
        local issue_title="[EPIC] ${rfc_id}: ${rfc_title}"
        
        local issue_body="# ${rfc_id}: ${rfc_title}

## Summary

${rfc_summary}

## Motivation

${rfc_motivation}

## Scope

- **Tasks:** ${task_count}
- **Acceptance Criteria:** ${ac_count}

## Tasks

"
        # List all tasks as checklist
        local task_list=$(jq -r '.tasks[] | "- [ ] \(.id): \(.title)"' "$rfc_file")
        issue_body+="${task_list}

## Acceptance Criteria

"
        # List all AC
        local ac_list=$(jq -r '.acceptance_criteria[] | "- [ ] **\(.id)** [\(.priority)]: \(.criterion)"' "$rfc_file")
        issue_body+="${ac_list}

## References

"
        local ref_list=$(jq -r '.references[] | "- [\(.title)](\(.url))"' "$rfc_file")
        issue_body+="${ref_list}"
        
        if [[ "$DRY_RUN" == "--dry-run" ]]; then
            log_info "[DRY-RUN] Would create epic: $issue_title"
        else
            if gh issue create \
                --repo "$REPO" \
                --title "$issue_title" \
                --body "$issue_body" \
                --label "epic" 2>/dev/null; then
                log_success "Created epic: $issue_title"
            else
                log_error "Failed to create epic: $issue_title"
            fi
            sleep 1
        fi
    done
}

# Main
main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║       RFC to GitHub Issues Importer                       ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    
    if [[ "$DRY_RUN" == "--dry-run" ]]; then
        log_warn "DRY RUN MODE - No changes will be made"
        echo ""
    fi
    
    check_prerequisites
    
    echo ""
    read -p "This will create ~80 issues. Continue? (y/N) " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted"
        exit 0
    fi
    
    create_labels
    create_milestones
    create_epic_issues
    create_issues
    
    echo ""
    log_success "Import complete!"
    echo ""
    echo "View issues at: https://github.com/${REPO}/issues"
    echo ""
}

main "$@"
