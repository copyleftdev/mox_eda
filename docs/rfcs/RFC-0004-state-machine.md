# RFC-0004: State Machine

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Authors** | Platform Team |
| **Created** | 2024-12-03 |

## Abstract

The state machine is the heart of Mox. It processes commands, produces events, maintains current state, and enforces all business invariants. This RFC defines how the state machine is structured, how events are applied, and how domains interact.

## Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STATE MACHINE                                      │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                         COMMAND PROCESSOR                                 │ │
│  │                                                                           │ │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │ │
│  │   │  Validate   │───►│   Execute   │───►│  Produce    │                  │ │
│  │   │  Command    │    │   Logic     │    │  Events     │                  │ │
│  │   └─────────────┘    └─────────────┘    └─────────────┘                  │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│                                      │ Events                                   │
│                                      ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                         EVENT APPLIER                                     │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                 Domain Event Handlers                           │    │ │
│  │   │                                                                 │    │ │
│  │   │   Talent   Campaign   Contract   Tenant   Analytics   ...       │    │ │
│  │   │                                                                 │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                      │                                    │ │
│  │                                      ▼                                    │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                 State Stores                                    │    │ │
│  │   │                                                                 │    │ │
│  │   │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │    │ │
│  │   │   │ Entities │  │  Indexes │  │ Counters │  │Aggregates│       │    │ │
│  │   │   └──────────┘  └──────────┘  └──────────┘  └──────────┘       │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                         QUERY PROCESSOR                                   │ │
│  │                                                                           │ │
│  │   • Read from state stores (entities, indexes)                            │ │
│  │   • No side effects                                                       │ │
│  │   • Can run on any node (leader or follower)                              │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Command and Event Types

```rust
// src/state_machine/command.rs

use serde::{Deserialize, Serialize};

/// All commands that can modify state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Command {
    // Talent commands
    CreateTalent(CreateTalentCmd),
    UpdateTalent(UpdateTalentCmd),
    DeleteTalent(DeleteTalentCmd),
    ChangeTalentStatus(ChangeTalentStatusCmd),
    
    // Campaign commands
    CreateCampaign(CreateCampaignCmd),
    UpdateCampaign(UpdateCampaignCmd),
    AddTalentToCampaign(AddTalentToCampaignCmd),
    RemoveTalentFromCampaign(RemoveTalentFromCampaignCmd),
    
    // Contract commands
    CreateContract(CreateContractCmd),
    SignContract(SignContractCmd),
    CreateInvoice(CreateInvoiceCmd),
    RecordPayment(RecordPaymentCmd),
    
    // Tenant commands
    ProvisionTenant(ProvisionTenantCmd),
    UpdateSubscription(UpdateSubscriptionCmd),
    RecordUsage(RecordUsageCmd),
    
    // Outreach commands
    SendMessage(SendMessageCmd),
    RecordResponse(RecordResponseCmd),
    
    // Integration commands
    ConnectPlatform(ConnectPlatformCmd),
    SyncPlatformData(SyncPlatformDataCmd),
    ProcessWebhook(ProcessWebhookCmd),
}

/// Command envelope with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandEnvelope {
    pub id: CommandId,
    pub tenant_id: TenantId,
    pub actor: Actor,
    pub timestamp: DateTime<Utc>,
    pub command: Command,
}

/// Who issued the command
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Actor {
    User(UserId),
    ApiKey(ApiKeyId),
    System,
    Webhook { platform: Platform, event_id: String },
}
```

```rust
// src/state_machine/event.rs

/// All events that modify state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Event {
    // Talent events
    TalentCreated(TalentCreatedEvent),
    TalentUpdated(TalentUpdatedEvent),
    TalentDeleted(TalentDeletedEvent),
    TalentStatusChanged(TalentStatusChangedEvent),
    
    // Campaign events
    CampaignCreated(CampaignCreatedEvent),
    CampaignUpdated(CampaignUpdatedEvent),
    CampaignStatusChanged(CampaignStatusChangedEvent),
    TalentAddedToCampaign(TalentAddedToCampaignEvent),
    TalentRemovedFromCampaign(TalentRemovedFromCampaignEvent),
    DeliverableSubmitted(DeliverableSubmittedEvent),
    DeliverableApproved(DeliverableApprovedEvent),
    
    // Contract events
    ContractCreated(ContractCreatedEvent),
    ContractSigned(ContractSignedEvent),
    InvoiceCreated(InvoiceCreatedEvent),
    PaymentReceived(PaymentReceivedEvent),
    PayoutProcessed(PayoutProcessedEvent),
    
    // Tenant events
    TenantProvisioned(TenantProvisionedEvent),
    SubscriptionChanged(SubscriptionChangedEvent),
    UsageRecorded(UsageRecordedEvent),
    QuotaExceeded(QuotaExceededEvent),
    
    // Integration events
    PlatformConnected(PlatformConnectedEvent),
    PlatformSynced(PlatformSyncedEvent),
    WebhookProcessed(WebhookProcessedEvent),
}

/// Event envelope with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventEnvelope {
    pub id: EventId,
    pub tenant_id: TenantId,
    pub sequence: u64,
    pub timestamp: DateTime<Utc>,
    pub causation_id: CommandId,
    pub correlation_id: CorrelationId,
    pub event: Event,
}
```

## State Machine Implementation

```rust
// src/state_machine/mod.rs

pub struct StateMachine {
    // Domain states
    talents: TalentState,
    campaigns: CampaignState,
    contracts: ContractState,
    tenants: TenantState,
    outreach: OutreachState,
    integrations: IntegrationState,
    
    // Cross-cutting state
    counters: CounterState,
    indexes: IndexState,
    
    // Metrics
    events_applied: u64,
    last_applied_sequence: u64,
}

impl StateMachine {
    /// Process a command and return resulting events
    pub fn process(&mut self, cmd: &CommandEnvelope) -> Result<Vec<EventEnvelope>> {
        // Validate tenant exists and is active
        self.validate_tenant(&cmd.tenant_id)?;
        
        // Validate actor has permission
        self.validate_authorization(&cmd.tenant_id, &cmd.actor, &cmd.command)?;
        
        // Execute command
        let events = match &cmd.command {
            Command::CreateTalent(c) => self.create_talent(cmd, c)?,
            Command::UpdateTalent(c) => self.update_talent(cmd, c)?,
            Command::ChangeTalentStatus(c) => self.change_talent_status(cmd, c)?,
            Command::CreateCampaign(c) => self.create_campaign(cmd, c)?,
            Command::AddTalentToCampaign(c) => self.add_talent_to_campaign(cmd, c)?,
            Command::CreateContract(c) => self.create_contract(cmd, c)?,
            Command::SignContract(c) => self.sign_contract(cmd, c)?,
            Command::RecordUsage(c) => self.record_usage(cmd, c)?,
            // ... other commands
            _ => return Err(StateMachineError::UnknownCommand),
        };
        
        Ok(events)
    }
    
    /// Apply a committed event to state
    pub fn apply(&mut self, event: &EventEnvelope) -> Result<()> {
        match &event.event {
            Event::TalentCreated(e) => self.talents.apply_created(event, e)?,
            Event::TalentUpdated(e) => self.talents.apply_updated(event, e)?,
            Event::TalentDeleted(e) => self.talents.apply_deleted(event, e)?,
            Event::TalentStatusChanged(e) => self.talents.apply_status_changed(event, e)?,
            
            Event::CampaignCreated(e) => self.campaigns.apply_created(event, e)?,
            Event::CampaignUpdated(e) => self.campaigns.apply_updated(event, e)?,
            Event::TalentAddedToCampaign(e) => self.campaigns.apply_talent_added(event, e)?,
            
            Event::ContractCreated(e) => self.contracts.apply_created(event, e)?,
            Event::ContractSigned(e) => self.contracts.apply_signed(event, e)?,
            Event::PaymentReceived(e) => self.contracts.apply_payment(event, e)?,
            
            Event::TenantProvisioned(e) => self.tenants.apply_provisioned(event, e)?,
            Event::UsageRecorded(e) => self.tenants.apply_usage(event, e)?,
            
            // ... other events
            _ => {}
        }
        
        // Update cross-cutting state
        self.update_indexes(event)?;
        self.update_counters(event)?;
        
        self.events_applied += 1;
        self.last_applied_sequence = event.sequence;
        
        Ok(())
    }
    
    /// Create snapshot of current state
    pub fn snapshot(&self) -> Result<Vec<u8>> {
        let snapshot = StateMachineSnapshot {
            talents: self.talents.snapshot(),
            campaigns: self.campaigns.snapshot(),
            contracts: self.contracts.snapshot(),
            tenants: self.tenants.snapshot(),
            outreach: self.outreach.snapshot(),
            integrations: self.integrations.snapshot(),
            counters: self.counters.snapshot(),
            indexes: self.indexes.snapshot(),
            events_applied: self.events_applied,
            last_applied_sequence: self.last_applied_sequence,
        };
        
        rmp_serde::to_vec(&snapshot).map_err(Into::into)
    }
    
    /// Restore state from snapshot
    pub fn restore(&mut self, data: &[u8]) -> Result<()> {
        let snapshot: StateMachineSnapshot = rmp_serde::from_slice(data)?;
        
        self.talents.restore(snapshot.talents);
        self.campaigns.restore(snapshot.campaigns);
        self.contracts.restore(snapshot.contracts);
        self.tenants.restore(snapshot.tenants);
        self.outreach.restore(snapshot.outreach);
        self.integrations.restore(snapshot.integrations);
        self.counters.restore(snapshot.counters);
        self.indexes.restore(snapshot.indexes);
        self.events_applied = snapshot.events_applied;
        self.last_applied_sequence = snapshot.last_applied_sequence;
        
        Ok(())
    }
}
```

## Domain State Example: Talents

```rust
// src/domain/talent/state.rs

pub struct TalentState {
    /// Primary storage: talent_id -> Talent
    talents: BTreeMap<TalentId, Talent>,
    
    /// Index: tenant_id -> [talent_id]
    by_tenant: BTreeMap<TenantId, BTreeSet<TalentId>>,
    
    /// Index: org_id -> [talent_id]
    by_org: BTreeMap<OrgId, BTreeSet<TalentId>>,
    
    /// Index: status -> [talent_id]
    by_status: BTreeMap<TalentStatus, BTreeSet<TalentId>>,
    
    /// Index: platform_handle -> talent_id
    by_platform_handle: BTreeMap<(Platform, String), TalentId>,
}

impl TalentState {
    pub fn apply_created(&mut self, env: &EventEnvelope, event: &TalentCreatedEvent) -> Result<()> {
        // Check for duplicate
        if self.talents.contains_key(&event.talent_id) {
            return Err(StateMachineError::DuplicateEntity);
        }
        
        // Check for duplicate platform handle
        if let Some(handle) = &event.tiktok_handle {
            if self.by_platform_handle.contains_key(&(Platform::TikTok, handle.clone())) {
                return Err(StateMachineError::DuplicatePlatformHandle);
            }
        }
        
        let talent = Talent {
            id: event.talent_id,
            tenant_id: env.tenant_id,
            org_id: event.org_id,
            display_name: event.display_name.clone(),
            tiktok_handle: event.tiktok_handle.clone(),
            instagram_handle: event.instagram_handle.clone(),
            status: TalentStatus::Prospect,
            tier: event.tier,
            created_at: env.timestamp,
            updated_at: env.timestamp,
        };
        
        // Insert into primary storage
        self.talents.insert(event.talent_id, talent);
        
        // Update indexes
        self.by_tenant
            .entry(env.tenant_id)
            .or_default()
            .insert(event.talent_id);
        
        self.by_org
            .entry(event.org_id)
            .or_default()
            .insert(event.talent_id);
        
        self.by_status
            .entry(TalentStatus::Prospect)
            .or_default()
            .insert(event.talent_id);
        
        if let Some(handle) = &event.tiktok_handle {
            self.by_platform_handle
                .insert((Platform::TikTok, handle.clone()), event.talent_id);
        }
        
        Ok(())
    }
    
    pub fn apply_status_changed(&mut self, env: &EventEnvelope, event: &TalentStatusChangedEvent) -> Result<()> {
        let talent = self.talents.get_mut(&event.talent_id)
            .ok_or(StateMachineError::EntityNotFound)?;
        
        // Validate state transition
        if !talent.status.can_transition_to(&event.to_status) {
            return Err(StateMachineError::InvalidStateTransition);
        }
        
        // Update status index
        self.by_status
            .get_mut(&talent.status)
            .map(|set| set.remove(&event.talent_id));
        
        self.by_status
            .entry(event.to_status)
            .or_default()
            .insert(event.talent_id);
        
        // Update entity
        talent.status = event.to_status;
        talent.updated_at = env.timestamp;
        
        Ok(())
    }
    
    // Queries
    
    pub fn get(&self, id: &TalentId) -> Option<&Talent> {
        self.talents.get(id)
    }
    
    pub fn list_by_org(&self, org_id: &OrgId, limit: usize, offset: usize) -> Vec<&Talent> {
        self.by_org
            .get(org_id)
            .map(|ids| {
                ids.iter()
                    .skip(offset)
                    .take(limit)
                    .filter_map(|id| self.talents.get(id))
                    .collect()
            })
            .unwrap_or_default()
    }
    
    pub fn list_by_status(&self, status: TalentStatus) -> Vec<&Talent> {
        self.by_status
            .get(&status)
            .map(|ids| {
                ids.iter()
                    .filter_map(|id| self.talents.get(id))
                    .collect()
            })
            .unwrap_or_default()
    }
    
    pub fn find_by_handle(&self, platform: Platform, handle: &str) -> Option<&Talent> {
        self.by_platform_handle
            .get(&(platform, handle.to_string()))
            .and_then(|id| self.talents.get(id))
    }
}
```

## Command Processing Example

```rust
// src/state_machine/commands/talent.rs

impl StateMachine {
    pub fn create_talent(
        &self,
        cmd: &CommandEnvelope,
        create: &CreateTalentCmd,
    ) -> Result<Vec<EventEnvelope>> {
        // Validate org exists and belongs to tenant
        let org = self.tenants.get_org(&cmd.tenant_id, &create.org_id)
            .ok_or(StateMachineError::OrgNotFound)?;
        
        // Validate unique constraints
        if let Some(handle) = &create.tiktok_handle {
            if self.talents.find_by_handle(Platform::TikTok, handle).is_some() {
                return Err(StateMachineError::DuplicatePlatformHandle);
            }
        }
        
        // Generate event
        let event = TalentCreatedEvent {
            talent_id: TalentId::new(),
            org_id: create.org_id,
            display_name: create.display_name.clone(),
            tiktok_handle: create.tiktok_handle.clone(),
            instagram_handle: create.instagram_handle.clone(),
            tier: create.tier.unwrap_or(TalentTier::Unknown),
        };
        
        Ok(vec![EventEnvelope {
            id: EventId::new(),
            tenant_id: cmd.tenant_id,
            sequence: 0, // Will be set by consensus layer
            timestamp: cmd.timestamp,
            causation_id: cmd.id,
            correlation_id: CorrelationId::new(),
            event: Event::TalentCreated(event),
        }])
    }
    
    pub fn change_talent_status(
        &self,
        cmd: &CommandEnvelope,
        change: &ChangeTalentStatusCmd,
    ) -> Result<Vec<EventEnvelope>> {
        // Get current talent
        let talent = self.talents.get(&change.talent_id)
            .ok_or(StateMachineError::EntityNotFound)?;
        
        // Validate tenant
        if talent.tenant_id != cmd.tenant_id {
            return Err(StateMachineError::TenantMismatch);
        }
        
        // Validate state transition
        if !talent.status.can_transition_to(&change.to_status) {
            return Err(StateMachineError::InvalidStateTransition);
        }
        
        let event = TalentStatusChangedEvent {
            talent_id: change.talent_id,
            from_status: talent.status,
            to_status: change.to_status,
            reason: change.reason.clone(),
        };
        
        Ok(vec![EventEnvelope {
            id: EventId::new(),
            tenant_id: cmd.tenant_id,
            sequence: 0,
            timestamp: cmd.timestamp,
            causation_id: cmd.id,
            correlation_id: CorrelationId::new(),
            event: Event::TalentStatusChanged(event),
        }])
    }
}
```

## Multi-Tenant Isolation

```rust
// src/state_machine/tenant_isolation.rs

impl StateMachine {
    /// Validate tenant exists and is active
    fn validate_tenant(&self, tenant_id: &TenantId) -> Result<()> {
        let tenant = self.tenants.get(tenant_id)
            .ok_or(StateMachineError::TenantNotFound)?;
        
        if tenant.status == TenantStatus::Suspended {
            return Err(StateMachineError::TenantSuspended);
        }
        
        if tenant.status == TenantStatus::Deleted {
            return Err(StateMachineError::TenantDeleted);
        }
        
        Ok(())
    }
    
    /// Validate authorization
    fn validate_authorization(
        &self,
        tenant_id: &TenantId,
        actor: &Actor,
        command: &Command,
    ) -> Result<()> {
        match actor {
            Actor::User(user_id) => {
                let user = self.tenants.get_user(tenant_id, user_id)
                    .ok_or(StateMachineError::UserNotFound)?;
                
                let permission = command.required_permission();
                if !user.has_permission(permission) {
                    return Err(StateMachineError::PermissionDenied);
                }
            }
            Actor::ApiKey(key_id) => {
                let key = self.tenants.get_api_key(tenant_id, key_id)
                    .ok_or(StateMachineError::ApiKeyNotFound)?;
                
                let permission = command.required_permission();
                if !key.has_permission(permission) {
                    return Err(StateMachineError::PermissionDenied);
                }
            }
            Actor::System => {
                // System can do anything
            }
            Actor::Webhook { .. } => {
                // Webhooks can only trigger specific commands
                if !command.allowed_from_webhook() {
                    return Err(StateMachineError::PermissionDenied);
                }
            }
        }
        
        Ok(())
    }
}
```

## Query Interface

```rust
// src/state_machine/query.rs

/// All queries (read-only operations)
pub enum Query {
    // Talent queries
    GetTalent { tenant_id: TenantId, talent_id: TalentId },
    ListTalents { tenant_id: TenantId, org_id: OrgId, filters: TalentFilters },
    SearchTalents { tenant_id: TenantId, query: String, limit: usize },
    
    // Campaign queries
    GetCampaign { tenant_id: TenantId, campaign_id: CampaignId },
    ListCampaigns { tenant_id: TenantId, org_id: OrgId, filters: CampaignFilters },
    
    // Contract queries
    GetContract { tenant_id: TenantId, contract_id: ContractId },
    ListInvoices { tenant_id: TenantId, filters: InvoiceFilters },
    
    // Analytics queries
    GetTenantStats { tenant_id: TenantId },
    GetOrgStats { tenant_id: TenantId, org_id: OrgId },
}

pub enum QueryResult {
    Talent(Option<Talent>),
    Talents(Vec<Talent>),
    Campaign(Option<Campaign>),
    Campaigns(Vec<Campaign>),
    Contract(Option<Contract>),
    Invoices(Vec<Invoice>),
    Stats(Stats),
}

impl StateMachine {
    /// Execute a query (read-only)
    pub fn query(&self, query: Query) -> Result<QueryResult> {
        match query {
            Query::GetTalent { tenant_id, talent_id } => {
                let talent = self.talents.get(&talent_id)
                    .filter(|t| t.tenant_id == tenant_id)
                    .cloned();
                Ok(QueryResult::Talent(talent))
            }
            Query::ListTalents { tenant_id, org_id, filters } => {
                let talents = self.talents.list_by_org(&org_id, filters.limit, filters.offset)
                    .into_iter()
                    .filter(|t| t.tenant_id == tenant_id)
                    .filter(|t| filters.matches(t))
                    .cloned()
                    .collect();
                Ok(QueryResult::Talents(talents))
            }
            Query::SearchTalents { tenant_id, query, limit } => {
                let talents = self.indexes.search_talents(&tenant_id, &query, limit)?;
                Ok(QueryResult::Talents(talents))
            }
            // ... other queries
            _ => Err(StateMachineError::UnknownQuery),
        }
    }
}
```

## Invariants

| Invariant | Enforcement |
|-----------|-------------|
| Entity IDs are globally unique | ULIDs with node-specific generation |
| Tenant isolation | Every query/command validates tenant_id |
| State transitions are valid | FSM validation in apply() |
| No orphaned references | Cascade validation in commands |
| Counters are accurate | Atomic updates in apply() |

## Performance Targets

| Operation | Target |
|-----------|--------|
| Command validation | < 10μs |
| Event application | < 50μs |
| Single entity query | < 10μs |
| List query (100 items) | < 1ms |
| Snapshot creation | < 1s per 1M entities |
| Snapshot restore | < 2s per 1M entities |

## References

- [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
- [CQRS](https://martinfowler.com/bliki/CQRS.html)
- [TigerBeetle State Machine](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/DESIGN.md#state-machine)
