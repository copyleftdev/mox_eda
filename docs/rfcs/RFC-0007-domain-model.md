# RFC-0007: Domain Model

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Authors** | Platform Team |
| **Created** | 2024-12-03 |

## Abstract

This RFC maps the AsyncAPI event specification to the TigerBeetle-style state machine. All 125+ event types from the spec are implemented as commands and events within the single binary.

## Domain Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN MODEL                                       │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           CORE DOMAINS                                  │   │
│  │                                                                         │   │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │   │
│  │   │   Tenant    │  │   Talent    │  │  Campaign   │  │  Contract   │   │   │
│  │   │             │  │             │  │             │  │             │   │   │
│  │   │ • Orgs      │  │ • Profiles  │  │ • Projects  │  │ • Agreements│   │   │
│  │   │ • Users     │  │ • Socials   │  │ • Deliverbl │  │ • Invoices  │   │   │
│  │   │ • Plans     │  │ • Metrics   │  │ • Schedules │  │ • Payouts   │   │   │
│  │   │ • Quotas    │  │ • Notes     │  │ • Briefs    │  │ • Terms     │   │   │
│  │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         SUPPORTING DOMAINS                              │   │
│  │                                                                         │   │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │   │
│  │   │  Outreach   │  │ Integration │  │  Analytics  │  │   Billing   │   │   │
│  │   │             │  │             │  │             │  │   (Stripe)  │   │   │
│  │   │ • Sequences │  │ • Platforms │  │ • Metrics   │  │ • Subscript │   │   │
│  │   │ • Messages  │  │ • Webhooks  │  │ • Reports   │  │ • Usage     │   │   │
│  │   │ • Templates │  │ • Syncs     │  │ • Funnels   │  │ • Metering  │   │   │
│  │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Tenant Domain

Multi-tenancy is fundamental. Every entity belongs to a tenant.

```rust
// src/domain/tenant/mod.rs

/// Tenant aggregate
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tenant {
    pub id: TenantId,
    pub name: String,
    pub slug: String,
    pub status: TenantStatus,
    pub plan: Plan,
    pub quotas: Quotas,
    pub settings: TenantSettings,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum TenantStatus {
    Active,
    Trial,
    Suspended,
    Cancelled,
}

/// Organization within a tenant
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Organization {
    pub id: OrgId,
    pub tenant_id: TenantId,
    pub name: String,
    pub settings: OrgSettings,
    pub created_at: DateTime<Utc>,
}

/// User within a tenant
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: UserId,
    pub tenant_id: TenantId,
    pub email: String,
    pub name: String,
    pub role: Role,
    pub orgs: Vec<OrgId>,
    pub permissions: Vec<Permission>,
    pub created_at: DateTime<Utc>,
}

/// Usage quotas
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Quotas {
    pub max_talents: u32,
    pub max_campaigns: u32,
    pub max_users: u32,
    pub max_api_calls_per_month: u64,
    pub max_storage_bytes: u64,
}

// Commands
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TenantCommand {
    Provision(ProvisionTenantCmd),
    UpdatePlan(UpdatePlanCmd),
    Suspend(SuspendTenantCmd),
    Reactivate(ReactivateTenantCmd),
    CreateOrg(CreateOrgCmd),
    CreateUser(CreateUserCmd),
    UpdateQuotas(UpdateQuotasCmd),
    RecordUsage(RecordUsageCmd),
}

// Events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TenantEvent {
    Provisioned(TenantProvisionedEvent),
    PlanChanged(PlanChangedEvent),
    Suspended(TenantSuspendedEvent),
    Reactivated(TenantReactivatedEvent),
    OrgCreated(OrgCreatedEvent),
    UserCreated(UserCreatedEvent),
    QuotasUpdated(QuotasUpdatedEvent),
    UsageRecorded(UsageRecordedEvent),
    QuotaExceeded(QuotaExceededEvent),
}
```

## Talent Domain

```rust
// src/domain/talent/mod.rs

/// Talent aggregate
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Talent {
    pub id: TalentId,
    pub tenant_id: TenantId,
    pub org_id: OrgId,
    
    // Profile
    pub display_name: String,
    pub bio: Option<String>,
    pub avatar_url: Option<String>,
    
    // Platform handles
    pub tiktok: Option<PlatformProfile>,
    pub instagram: Option<PlatformProfile>,
    pub youtube: Option<PlatformProfile>,
    pub twitter: Option<PlatformProfile>,
    
    // Contact
    pub email: Option<String>,
    pub phone: Option<String>,
    
    // Classification
    pub status: TalentStatus,
    pub tier: TalentTier,
    pub tags: Vec<String>,
    pub categories: Vec<String>,
    
    // Metrics (denormalized for fast access)
    pub total_followers: u64,
    pub engagement_rate: f64,
    
    // Metadata
    pub custom_fields: HashMap<String, serde_json::Value>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformProfile {
    pub handle: String,
    pub external_id: Option<String>,
    pub follower_count: u64,
    pub following_count: u64,
    pub post_count: u64,
    pub engagement_rate: f64,
    pub verified: bool,
    pub last_synced_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum TalentStatus {
    Prospect,
    Contacted,
    Negotiating,
    Signed,
    Active,
    Paused,
    Churned,
}

impl TalentStatus {
    pub fn can_transition_to(&self, to: &TalentStatus) -> bool {
        use TalentStatus::*;
        matches!(
            (self, to),
            (Prospect, Contacted) |
            (Contacted, Negotiating) |
            (Contacted, Churned) |
            (Negotiating, Signed) |
            (Negotiating, Churned) |
            (Signed, Active) |
            (Active, Paused) |
            (Active, Churned) |
            (Paused, Active) |
            (Paused, Churned)
        )
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum TalentTier {
    Unknown,
    Nano,      // < 10K
    Micro,     // 10K - 100K
    Mid,       // 100K - 500K
    Macro,     // 500K - 1M
    Mega,      // > 1M
}

impl TalentTier {
    pub fn from_followers(count: u64) -> Self {
        match count {
            0..=9_999 => TalentTier::Nano,
            10_000..=99_999 => TalentTier::Micro,
            100_000..=499_999 => TalentTier::Mid,
            500_000..=999_999 => TalentTier::Macro,
            _ => TalentTier::Mega,
        }
    }
}

// Commands
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TalentCommand {
    Create(CreateTalentCmd),
    Update(UpdateTalentCmd),
    Delete(DeleteTalentCmd),
    ChangeStatus(ChangeTalentStatusCmd),
    LinkPlatform(LinkPlatformCmd),
    UpdateMetrics(UpdateTalentMetricsCmd),
    AddNote(AddTalentNoteCmd),
    AddTag(AddTagCmd),
    RemoveTag(RemoveTagCmd),
}

// Events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TalentEvent {
    Created(TalentCreatedEvent),
    Updated(TalentUpdatedEvent),
    Deleted(TalentDeletedEvent),
    StatusChanged(TalentStatusChangedEvent),
    PlatformLinked(PlatformLinkedEvent),
    MetricsUpdated(TalentMetricsUpdatedEvent),
    NoteAdded(TalentNoteAddedEvent),
    TagAdded(TagAddedEvent),
    TagRemoved(TagRemovedEvent),
}
```

## Campaign Domain

```rust
// src/domain/campaign/mod.rs

/// Campaign aggregate
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Campaign {
    pub id: CampaignId,
    pub tenant_id: TenantId,
    pub org_id: OrgId,
    
    // Details
    pub name: String,
    pub description: Option<String>,
    pub brand_id: Option<BrandId>,
    
    // Status
    pub status: CampaignStatus,
    pub campaign_type: CampaignType,
    
    // Timeline
    pub start_date: Option<NaiveDate>,
    pub end_date: Option<NaiveDate>,
    
    // Budget
    pub budget: Option<Money>,
    pub spent: Money,
    
    // Goals
    pub goals: CampaignGoals,
    
    // Talents
    pub talent_ids: Vec<TalentId>,
    
    // Deliverables
    pub deliverables: Vec<Deliverable>,
    
    // Metadata
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Deliverable {
    pub id: DeliverableId,
    pub campaign_id: CampaignId,
    pub talent_id: TalentId,
    
    pub title: String,
    pub description: Option<String>,
    pub platform: Platform,
    pub content_type: ContentType,
    
    pub status: DeliverableStatus,
    pub due_date: Option<NaiveDate>,
    
    pub content_url: Option<String>,
    pub submitted_at: Option<DateTime<Utc>>,
    pub approved_at: Option<DateTime<Utc>>,
    
    pub metrics: DeliverableMetrics,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum CampaignStatus {
    Draft,
    Planning,
    Active,
    Paused,
    Completed,
    Cancelled,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum DeliverableStatus {
    Pending,
    InProgress,
    Submitted,
    RevisionRequested,
    Approved,
    Published,
    Rejected,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CampaignGoals {
    pub target_reach: Option<u64>,
    pub target_engagement: Option<f64>,
    pub target_conversions: Option<u64>,
    pub target_roi: Option<f64>,
}

// Events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CampaignEvent {
    Created(CampaignCreatedEvent),
    Updated(CampaignUpdatedEvent),
    StatusChanged(CampaignStatusChangedEvent),
    TalentAdded(TalentAddedToCampaignEvent),
    TalentRemoved(TalentRemovedFromCampaignEvent),
    DeliverableCreated(DeliverableCreatedEvent),
    DeliverableSubmitted(DeliverableSubmittedEvent),
    DeliverableApproved(DeliverableApprovedEvent),
    DeliverableRejected(DeliverableRejectedEvent),
    BudgetUpdated(CampaignBudgetUpdatedEvent),
    Completed(CampaignCompletedEvent),
}
```

## Contract Domain

```rust
// src/domain/contract/mod.rs

/// Contract aggregate
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Contract {
    pub id: ContractId,
    pub tenant_id: TenantId,
    pub org_id: OrgId,
    
    // Parties
    pub talent_id: TalentId,
    pub campaign_id: Option<CampaignId>,
    
    // Terms
    pub contract_type: ContractType,
    pub status: ContractStatus,
    pub total_value: Money,
    pub payment_terms: PaymentTerms,
    
    // Timeline
    pub start_date: NaiveDate,
    pub end_date: Option<NaiveDate>,
    
    // Signatures
    pub signed_at: Option<DateTime<Utc>>,
    pub signed_by_talent: bool,
    pub signed_by_org: bool,
    
    // Documents
    pub document_url: Option<String>,
    
    // Related
    pub invoices: Vec<InvoiceId>,
    pub payouts: Vec<PayoutId>,
    
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Invoice {
    pub id: InvoiceId,
    pub contract_id: ContractId,
    pub tenant_id: TenantId,
    
    pub invoice_number: String,
    pub status: InvoiceStatus,
    
    pub amount: Money,
    pub due_date: NaiveDate,
    
    pub line_items: Vec<LineItem>,
    
    pub stripe_invoice_id: Option<String>,
    pub paid_at: Option<DateTime<Utc>>,
    
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Payout {
    pub id: PayoutId,
    pub talent_id: TalentId,
    pub contract_id: ContractId,
    pub tenant_id: TenantId,
    
    pub status: PayoutStatus,
    pub amount: Money,
    
    pub stripe_transfer_id: Option<String>,
    pub stripe_payout_id: Option<String>,
    
    pub scheduled_date: Option<NaiveDate>,
    pub paid_at: Option<DateTime<Utc>>,
    
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Money {
    pub amount_cents: i64,
    pub currency: Currency,
}

// Events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ContractEvent {
    Created(ContractCreatedEvent),
    Signed(ContractSignedEvent),
    Terminated(ContractTerminatedEvent),
    InvoiceCreated(InvoiceCreatedEvent),
    InvoiceSent(InvoiceSentEvent),
    PaymentReceived(PaymentReceivedEvent),
    PaymentFailed(PaymentFailedEvent),
    PayoutScheduled(PayoutScheduledEvent),
    PayoutProcessed(PayoutProcessedEvent),
    PayoutFailed(PayoutFailedEvent),
}
```

## Integration Domain

```rust
// src/domain/integration/mod.rs

/// Platform connection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformConnection {
    pub id: ConnectionId,
    pub tenant_id: TenantId,
    pub platform: Platform,
    
    pub external_user_id: String,
    pub status: ConnectionStatus,
    
    pub scopes: Vec<String>,
    pub token_expires_at: Option<DateTime<Utc>>,
    
    pub last_synced_at: Option<DateTime<Utc>>,
    pub sync_status: SyncStatus,
    
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum Platform {
    TikTok,
    Instagram,
    YouTube,
    Twitter,
    Twitch,
    Facebook,
    LinkedIn,
    Spotify,
    Pinterest,
    Snapchat,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum ConnectionStatus {
    Active,
    Expired,
    Revoked,
    Error,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebhookEvent {
    pub id: WebhookEventId,
    pub tenant_id: TenantId,
    pub platform: Platform,
    
    pub event_type: String,
    pub external_id: String,
    pub payload: serde_json::Value,
    
    pub processed: bool,
    pub processed_at: Option<DateTime<Utc>>,
    pub error: Option<String>,
    
    pub received_at: DateTime<Utc>,
}

// Events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum IntegrationEvent {
    PlatformConnected(PlatformConnectedEvent),
    PlatformDisconnected(PlatformDisconnectedEvent),
    TokenRefreshed(TokenRefreshedEvent),
    SyncStarted(SyncStartedEvent),
    SyncCompleted(SyncCompletedEvent),
    SyncFailed(SyncFailedEvent),
    WebhookReceived(WebhookReceivedEvent),
    WebhookProcessed(WebhookProcessedEvent),
    ContentSynced(ContentSyncedEvent),
    MetricsSynced(MetricsSyncedEvent),
}
```

## Analytics Domain

```rust
// src/domain/analytics/mod.rs

/// Metric recording
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Metric {
    pub id: MetricId,
    pub tenant_id: TenantId,
    pub org_id: Option<OrgId>,
    
    pub name: MetricName,
    pub value: f64,
    pub dimensions: HashMap<String, String>,
    pub tags: Vec<String>,
    
    pub timestamp: DateTime<Utc>,
}

/// Pre-computed aggregation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Aggregation {
    pub id: AggregationId,
    pub tenant_id: TenantId,
    
    pub metric_name: MetricName,
    pub aggregation_type: AggregationType,
    pub granularity: TimeGranularity,
    
    pub period_start: DateTime<Utc>,
    pub period_end: DateTime<Utc>,
    
    pub values: AggregatedValues,
    pub sample_count: u64,
    
    pub computed_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AggregatedValues {
    pub sum: f64,
    pub avg: f64,
    pub min: f64,
    pub max: f64,
    pub p50: f64,
    pub p90: f64,
    pub p95: f64,
    pub p99: f64,
}

/// Funnel definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Funnel {
    pub id: FunnelId,
    pub tenant_id: TenantId,
    
    pub name: String,
    pub stages: Vec<FunnelStage>,
    
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FunnelStage {
    pub name: String,
    pub event_type: String,
    pub order: u32,
}

/// Cohort definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Cohort {
    pub id: CohortId,
    pub tenant_id: TenantId,
    
    pub cohort_type: CohortType,
    pub period: String,
    
    pub members: Vec<EntityId>,
    pub size: u64,
    
    pub created_at: DateTime<Utc>,
}

// Events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AnalyticsEvent {
    MetricRecorded(MetricRecordedEvent),
    AggregationComputed(AggregationComputedEvent),
    FunnelAnalyzed(FunnelAnalyzedEvent),
    CohortAnalyzed(CohortAnalyzedEvent),
    AnomalyDetected(AnomalyDetectedEvent),
    ReportGenerated(ReportGeneratedEvent),
    AlertTriggered(AlertTriggeredEvent),
}
```

## State Machine Integration

All domains plug into the unified state machine:

```rust
// src/state_machine/mod.rs

impl StateMachine {
    pub fn process(&mut self, cmd: &CommandEnvelope) -> Result<Vec<EventEnvelope>> {
        match &cmd.command {
            // Tenant commands
            Command::Tenant(c) => self.tenant_domain.process(cmd, c),
            
            // Talent commands
            Command::Talent(c) => self.talent_domain.process(cmd, c),
            
            // Campaign commands
            Command::Campaign(c) => self.campaign_domain.process(cmd, c),
            
            // Contract commands
            Command::Contract(c) => self.contract_domain.process(cmd, c),
            
            // Integration commands
            Command::Integration(c) => self.integration_domain.process(cmd, c),
            
            // Analytics commands
            Command::Analytics(c) => self.analytics_domain.process(cmd, c),
            
            // Outreach commands
            Command::Outreach(c) => self.outreach_domain.process(cmd, c),
        }
    }
    
    pub fn apply(&mut self, event: &EventEnvelope) -> Result<()> {
        match &event.event {
            Event::Tenant(e) => self.tenant_domain.apply(event, e)?,
            Event::Talent(e) => self.talent_domain.apply(event, e)?,
            Event::Campaign(e) => self.campaign_domain.apply(event, e)?,
            Event::Contract(e) => self.contract_domain.apply(event, e)?,
            Event::Integration(e) => self.integration_domain.apply(event, e)?,
            Event::Analytics(e) => self.analytics_domain.apply(event, e)?,
            Event::Outreach(e) => self.outreach_domain.apply(event, e)?,
        }
        
        // Cross-domain projections
        self.update_search_index(event)?;
        self.update_analytics_counters(event)?;
        
        Ok(())
    }
}
```

## Event Count Summary

| Domain | Events | Commands |
|--------|--------|----------|
| Tenant | 12 | 10 |
| Talent | 15 | 12 |
| Campaign | 18 | 14 |
| Contract | 16 | 12 |
| Outreach | 10 | 8 |
| Integration | 14 | 10 |
| Analytics | 22 | 15 |
| Billing (Stripe) | 18 | 10 |
| **Total** | **125** | **91** |

## References

- [Mox AsyncAPI Specification](../../asyncapi.yaml)
- [Domain-Driven Design](https://www.domainlanguage.com/ddd/)
- [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
