# RFC-0008: API Layer

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Authors** | Platform Team |
| **Created** | 2024-12-03 |

## Abstract

This RFC defines the HTTP API layer for client communication, including REST endpoints, WebSocket subscriptions, webhook handling, and authentication. All API code runs within the single binary.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                API LAYER                                        │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                           HTTP SERVER (Axum)                              │ │
│  │                                                                           │ │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │ │
│  │   │    REST     │  │  WebSocket  │  │  Webhooks   │  │   Health    │     │ │
│  │   │   /api/v1   │  │    /ws      │  │ /webhooks/* │  │  /health    │     │ │
│  │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │ │
│  │          │                │                │                │             │ │
│  │          └────────────────┴────────────────┴────────────────┘             │ │
│  │                                   │                                       │ │
│  └───────────────────────────────────┼───────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────┼───────────────────────────────────────┐ │
│  │                                   ▼          MIDDLEWARE STACK             │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │  Request ID → Tracing → Auth → Tenant → RateLimit → Timeout    │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────┼───────────────────────────────────────┐ │
│  │                                   ▼          REQUEST HANDLING             │ │
│  │                                                                           │ │
│  │   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐      │ │
│  │   │   Write Path    │    │   Read Path     │    │  Subscribe Path │      │ │
│  │   │                 │    │                 │    │                 │      │ │
│  │   │ • Validate      │    │ • Query state   │    │ • Register sub  │      │ │
│  │   │ • Build command │    │ • Return data   │    │ • Stream events │      │ │
│  │   │ • Submit to Raft│    │ • Cache headers │    │ • Filter/map    │      │ │
│  │   │ • Await commit  │    │                 │    │                 │      │ │
│  │   │ • Return result │    │                 │    │                 │      │ │
│  │   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘      │ │
│  │            │                      │                      │                │ │
│  └────────────┼──────────────────────┼──────────────────────┼────────────────┘ │
│               │                      │                      │                  │
│               ▼                      ▼                      ▼                  │
│   ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐         │
│   │  Consensus Layer  │  │   State Machine   │  │   Event Stream    │         │
│   │      (Raft)       │  │     (Query)       │  │   (Broadcast)     │         │
│   └───────────────────┘  └───────────────────┘  └───────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Router Setup

```rust
// src/api/router.rs

use axum::{
    Router,
    routing::{get, post, put, delete},
    middleware,
};

pub fn create_router(state: AppState) -> Router {
    Router::new()
        // Health & metrics (no auth)
        .route("/health", get(health_handler))
        .route("/ready", get(ready_handler))
        .route("/metrics", get(metrics_handler))
        
        // API v1
        .nest("/api/v1", api_v1_router())
        
        // WebSocket
        .route("/ws", get(websocket_handler))
        
        // Webhooks (signature auth)
        .nest("/webhooks", webhook_router())
        
        // Middleware stack (bottom to top)
        .layer(middleware::from_fn(timeout_middleware))
        .layer(middleware::from_fn(rate_limit_middleware))
        .layer(middleware::from_fn_with_state(state.clone(), tenant_middleware))
        .layer(middleware::from_fn_with_state(state.clone(), auth_middleware))
        .layer(middleware::from_fn(tracing_middleware))
        .layer(middleware::from_fn(request_id_middleware))
        
        .with_state(state)
}

fn api_v1_router() -> Router<AppState> {
    Router::new()
        // Talents
        .route("/talents", get(list_talents).post(create_talent))
        .route("/talents/:id", get(get_talent).put(update_talent).delete(delete_talent))
        .route("/talents/:id/status", put(change_talent_status))
        .route("/talents/:id/notes", get(list_talent_notes).post(add_talent_note))
        .route("/talents/search", post(search_talents))
        
        // Campaigns
        .route("/campaigns", get(list_campaigns).post(create_campaign))
        .route("/campaigns/:id", get(get_campaign).put(update_campaign))
        .route("/campaigns/:id/talents", post(add_talent_to_campaign).delete(remove_talent_from_campaign))
        .route("/campaigns/:id/deliverables", get(list_deliverables).post(create_deliverable))
        .route("/campaigns/:id/deliverables/:deliverable_id", put(update_deliverable))
        .route("/campaigns/:id/deliverables/:deliverable_id/submit", post(submit_deliverable))
        .route("/campaigns/:id/deliverables/:deliverable_id/approve", post(approve_deliverable))
        
        // Contracts
        .route("/contracts", get(list_contracts).post(create_contract))
        .route("/contracts/:id", get(get_contract))
        .route("/contracts/:id/sign", post(sign_contract))
        .route("/contracts/:id/invoices", get(list_invoices).post(create_invoice))
        .route("/contracts/:id/payouts", get(list_payouts))
        
        // Organizations
        .route("/orgs", get(list_orgs).post(create_org))
        .route("/orgs/:id", get(get_org).put(update_org))
        .route("/orgs/:id/users", get(list_org_users))
        
        // Integrations
        .route("/integrations/connect/:platform", get(oauth_init))
        .route("/integrations/callback/:platform", get(oauth_callback))
        .route("/integrations/connections", get(list_connections))
        .route("/integrations/connections/:id", delete(disconnect))
        .route("/integrations/sync/:platform", post(trigger_sync))
        
        // Analytics
        .route("/analytics/metrics", get(query_metrics))
        .route("/analytics/aggregations", get(query_aggregations))
        .route("/analytics/funnels", get(list_funnels).post(create_funnel))
        .route("/analytics/funnels/:id/analyze", get(analyze_funnel))
        .route("/analytics/cohorts/:type/:period", get(analyze_cohort))
        .route("/analytics/reports", get(list_reports).post(generate_report))
        
        // Settings
        .route("/settings", get(get_settings).put(update_settings))
        .route("/settings/api-keys", get(list_api_keys).post(create_api_key))
        .route("/settings/api-keys/:id", delete(revoke_api_key))
}
```

## Authentication Middleware

```rust
// src/api/middleware/auth.rs

use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::Response,
};
use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};

pub async fn auth_middleware(
    State(state): State<AppState>,
    mut request: Request,
    next: Next,
) -> Result<Response, ApiError> {
    // Skip auth for health endpoints
    if request.uri().path().starts_with("/health") || 
       request.uri().path().starts_with("/metrics") {
        return Ok(next.run(request).await);
    }
    
    // Extract token from header
    let auth_header = request
        .headers()
        .get("Authorization")
        .and_then(|h| h.to_str().ok())
        .ok_or(ApiError::Unauthorized("Missing Authorization header"))?;
    
    let token = auth_header
        .strip_prefix("Bearer ")
        .ok_or(ApiError::Unauthorized("Invalid Authorization format"))?;
    
    // Try JWT first
    if let Ok(claims) = validate_jwt(token, &state.jwt_config) {
        request.extensions_mut().insert(AuthContext::User(claims));
        return Ok(next.run(request).await);
    }
    
    // Try API key
    if token.starts_with("mox_") {
        let api_key = state.state_machine
            .validate_api_key(token)
            .await
            .map_err(|_| ApiError::Unauthorized("Invalid API key"))?;
        
        request.extensions_mut().insert(AuthContext::ApiKey(api_key));
        return Ok(next.run(request).await);
    }
    
    Err(ApiError::Unauthorized("Invalid token"))
}

#[derive(Debug, Clone)]
pub enum AuthContext {
    User(UserClaims),
    ApiKey(ApiKeyContext),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserClaims {
    pub sub: UserId,
    pub tenant_id: TenantId,
    pub org_ids: Vec<OrgId>,
    pub role: Role,
    pub permissions: Vec<Permission>,
    pub exp: i64,
}

#[derive(Debug, Clone)]
pub struct ApiKeyContext {
    pub id: ApiKeyId,
    pub tenant_id: TenantId,
    pub permissions: Vec<Permission>,
}
```

## Write Handler Example

```rust
// src/api/handlers/talent.rs

use axum::{
    extract::{Path, State, Json},
    http::StatusCode,
};

/// POST /api/v1/talents
pub async fn create_talent(
    State(state): State<AppState>,
    auth: AuthContext,
    Json(body): Json<CreateTalentRequest>,
) -> Result<(StatusCode, Json<TalentResponse>), ApiError> {
    // Validate permission
    auth.require_permission(Permission::TalentWrite)?;
    
    // Build command
    let command = CommandEnvelope {
        id: CommandId::new(),
        tenant_id: auth.tenant_id(),
        actor: auth.into_actor(),
        timestamp: Utc::now(),
        command: Command::Talent(TalentCommand::Create(CreateTalentCmd {
            org_id: body.org_id,
            display_name: body.display_name,
            tiktok_handle: body.tiktok_handle,
            instagram_handle: body.instagram_handle,
            tier: body.tier,
        })),
    };
    
    // Submit to Raft (waits for commit)
    let events = state.raft
        .submit_command(command)
        .await
        .map_err(|e| match e {
            RaftError::NotLeader(leader) => ApiError::Redirect(leader),
            RaftError::Timeout => ApiError::Timeout,
            e => ApiError::Internal(e.to_string()),
        })?;
    
    // Extract created talent from events
    let talent_id = events.iter()
        .find_map(|e| match &e.event {
            Event::Talent(TalentEvent::Created(c)) => Some(c.talent_id),
            _ => None,
        })
        .ok_or(ApiError::Internal("No talent created event"))?;
    
    // Fetch the created talent
    let talent = state.state_machine
        .query(Query::GetTalent {
            tenant_id: auth.tenant_id(),
            talent_id,
        })
        .await?
        .into_talent()
        .ok_or(ApiError::NotFound)?;
    
    Ok((StatusCode::CREATED, Json(talent.into())))
}

/// GET /api/v1/talents/:id
pub async fn get_talent(
    State(state): State<AppState>,
    auth: AuthContext,
    Path(id): Path<TalentId>,
) -> Result<Json<TalentResponse>, ApiError> {
    // Validate permission
    auth.require_permission(Permission::TalentRead)?;
    
    // Query state machine directly (no Raft needed for reads)
    let talent = state.state_machine
        .query(Query::GetTalent {
            tenant_id: auth.tenant_id(),
            talent_id: id,
        })
        .await?
        .into_talent()
        .ok_or(ApiError::NotFound)?;
    
    Ok(Json(talent.into()))
}

/// PUT /api/v1/talents/:id/status
pub async fn change_talent_status(
    State(state): State<AppState>,
    auth: AuthContext,
    Path(id): Path<TalentId>,
    Json(body): Json<ChangeStatusRequest>,
) -> Result<Json<TalentResponse>, ApiError> {
    auth.require_permission(Permission::TalentWrite)?;
    
    let command = CommandEnvelope {
        id: CommandId::new(),
        tenant_id: auth.tenant_id(),
        actor: auth.into_actor(),
        timestamp: Utc::now(),
        command: Command::Talent(TalentCommand::ChangeStatus(ChangeTalentStatusCmd {
            talent_id: id,
            to_status: body.status,
            reason: body.reason,
        })),
    };
    
    state.raft.submit_command(command).await?;
    
    let talent = state.state_machine
        .query(Query::GetTalent {
            tenant_id: auth.tenant_id(),
            talent_id: id,
        })
        .await?
        .into_talent()
        .ok_or(ApiError::NotFound)?;
    
    Ok(Json(talent.into()))
}
```

## WebSocket Handler

```rust
// src/api/websocket.rs

use axum::{
    extract::{WebSocketUpgrade, State, Query},
    response::Response,
};
use axum::extract::ws::{WebSocket, Message};
use futures::{StreamExt, SinkExt};

pub async fn websocket_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
    Query(params): Query<WebSocketParams>,
) -> Response {
    ws.on_upgrade(move |socket| handle_socket(socket, state, params))
}

async fn handle_socket(
    socket: WebSocket,
    state: AppState,
    params: WebSocketParams,
) {
    let (mut sender, mut receiver) = socket.split();
    
    // Authenticate
    let auth = match validate_ws_token(&params.token, &state).await {
        Ok(auth) => auth,
        Err(_) => {
            let _ = sender.send(Message::Close(None)).await;
            return;
        }
    };
    
    // Subscribe to events
    let mut event_rx = state.event_bus.subscribe(auth.tenant_id());
    
    // Filter events based on subscription
    let filter = parse_subscription_filter(&params.subscribe);
    
    // Handle messages
    loop {
        tokio::select! {
            // Incoming message from client
            Some(msg) = receiver.next() => {
                match msg {
                    Ok(Message::Text(text)) => {
                        // Handle subscription changes
                        if let Ok(sub) = serde_json::from_str::<SubscriptionChange>(&text) {
                            // Update filter
                        }
                    }
                    Ok(Message::Ping(data)) => {
                        let _ = sender.send(Message::Pong(data)).await;
                    }
                    Ok(Message::Close(_)) => break,
                    Err(_) => break,
                    _ => {}
                }
            }
            
            // Event from bus
            Ok(event) = event_rx.recv() => {
                if filter.matches(&event) {
                    let json = serde_json::to_string(&event).unwrap();
                    if sender.send(Message::Text(json)).await.is_err() {
                        break;
                    }
                }
            }
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct WebSocketParams {
    token: String,
    subscribe: Option<String>,
}

#[derive(Debug)]
pub struct SubscriptionFilter {
    event_types: Option<Vec<String>>,
    entity_types: Option<Vec<String>>,
    entity_ids: Option<Vec<String>>,
}

impl SubscriptionFilter {
    pub fn matches(&self, event: &EventEnvelope) -> bool {
        // Check event type
        if let Some(types) = &self.event_types {
            if !types.iter().any(|t| event.event.type_name().contains(t)) {
                return false;
            }
        }
        
        // Check entity type
        if let Some(types) = &self.entity_types {
            if !types.iter().any(|t| event.event.entity_type() == Some(t)) {
                return false;
            }
        }
        
        // Check entity ID
        if let Some(ids) = &self.entity_ids {
            if !event.event.entity_id().map(|id| ids.contains(&id.to_string())).unwrap_or(false) {
                return false;
            }
        }
        
        true
    }
}
```

## Webhook Handler

```rust
// src/api/webhooks.rs

use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    body::Bytes,
};

/// POST /webhooks/:platform/:tenant_id
pub async fn webhook_handler(
    State(state): State<AppState>,
    Path((platform, tenant_id)): Path<(String, TenantId)>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<StatusCode, ApiError> {
    let platform = Platform::from_str(&platform)
        .map_err(|_| ApiError::BadRequest("Unknown platform"))?;
    
    // Get webhook secret for tenant/platform
    let secret = state.state_machine
        .get_webhook_secret(&tenant_id, platform)
        .await
        .ok_or(ApiError::NotFound)?;
    
    // Verify signature
    let signature = headers
        .get(platform.signature_header())
        .and_then(|h| h.to_str().ok())
        .ok_or(ApiError::Unauthorized("Missing signature"))?;
    
    if !verify_webhook_signature(platform, &body, signature, &secret) {
        return Err(ApiError::Unauthorized("Invalid signature"));
    }
    
    // Parse webhook payload
    let events = parse_webhook(platform, &body)?;
    
    // Submit as commands
    for event in events {
        let command = CommandEnvelope {
            id: CommandId::new(),
            tenant_id: tenant_id.clone(),
            actor: Actor::Webhook {
                platform,
                event_id: event.id.clone(),
            },
            timestamp: Utc::now(),
            command: Command::Integration(IntegrationCommand::ProcessWebhook(
                ProcessWebhookCmd {
                    platform,
                    event_type: event.event_type,
                    payload: event.payload,
                }
            )),
        };
        
        // Fire and forget (webhook processing is async)
        let _ = state.raft.submit_command(command).await;
    }
    
    Ok(StatusCode::OK)
}

fn verify_webhook_signature(
    platform: Platform,
    payload: &[u8],
    signature: &str,
    secret: &str,
) -> bool {
    match platform {
        Platform::TikTok | Platform::Stripe => {
            // HMAC-SHA256
            use hmac::{Hmac, Mac};
            use sha2::Sha256;
            
            let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).unwrap();
            mac.update(payload);
            let expected = hex::encode(mac.finalize().into_bytes());
            
            signature == expected
        }
        Platform::Instagram | Platform::Facebook => {
            // SHA1 with "sha1=" prefix
            let sig = signature.strip_prefix("sha1=").unwrap_or(signature);
            
            use hmac::{Hmac, Mac};
            use sha1::Sha1;
            
            let mut mac = Hmac::<Sha1>::new_from_slice(secret.as_bytes()).unwrap();
            mac.update(payload);
            let expected = hex::encode(mac.finalize().into_bytes());
            
            sig == expected
        }
        _ => {
            // Default: HMAC-SHA256
            use hmac::{Hmac, Mac};
            use sha2::Sha256;
            
            let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).unwrap();
            mac.update(payload);
            let expected = hex::encode(mac.finalize().into_bytes());
            
            signature == expected
        }
    }
}
```

## Error Handling

```rust
// src/api/error.rs

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};

#[derive(Debug)]
pub enum ApiError {
    BadRequest(String),
    Unauthorized(String),
    Forbidden(String),
    NotFound,
    Conflict(String),
    RateLimited,
    Timeout,
    Redirect(NodeId),
    Internal(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, error_type, message) = match self {
            ApiError::BadRequest(msg) => (StatusCode::BAD_REQUEST, "bad_request", msg),
            ApiError::Unauthorized(msg) => (StatusCode::UNAUTHORIZED, "unauthorized", msg),
            ApiError::Forbidden(msg) => (StatusCode::FORBIDDEN, "forbidden", msg),
            ApiError::NotFound => (StatusCode::NOT_FOUND, "not_found", "Resource not found".to_string()),
            ApiError::Conflict(msg) => (StatusCode::CONFLICT, "conflict", msg),
            ApiError::RateLimited => (StatusCode::TOO_MANY_REQUESTS, "rate_limited", "Rate limit exceeded".to_string()),
            ApiError::Timeout => (StatusCode::GATEWAY_TIMEOUT, "timeout", "Request timeout".to_string()),
            ApiError::Redirect(leader) => {
                return (
                    StatusCode::TEMPORARY_REDIRECT,
                    [("Location", format!("//{}", leader.address()))],
                ).into_response();
            }
            ApiError::Internal(msg) => (StatusCode::INTERNAL_SERVER_ERROR, "internal_error", msg),
        };
        
        let body = Json(ErrorResponse {
            error: ErrorBody {
                r#type: error_type.to_string(),
                message,
            },
        });
        
        (status, body).into_response()
    }
}

#[derive(Serialize)]
struct ErrorResponse {
    error: ErrorBody,
}

#[derive(Serialize)]
struct ErrorBody {
    r#type: String,
    message: String,
}
```

## Rate Limiting

```rust
// src/api/middleware/rate_limit.rs

use std::sync::Arc;
use dashmap::DashMap;

pub struct RateLimiter {
    /// Requests per tenant per window
    tenant_limits: DashMap<TenantId, TokenBucket>,
    
    /// Requests per IP per window (for unauthenticated)
    ip_limits: DashMap<IpAddr, TokenBucket>,
    
    /// Configuration
    config: RateLimitConfig,
}

pub struct RateLimitConfig {
    pub requests_per_second: u32,
    pub burst_size: u32,
}

struct TokenBucket {
    tokens: f64,
    last_update: Instant,
    rate: f64,
    capacity: f64,
}

impl TokenBucket {
    fn try_acquire(&mut self) -> bool {
        let now = Instant::now();
        let elapsed = now.duration_since(self.last_update).as_secs_f64();
        
        // Refill tokens
        self.tokens = (self.tokens + elapsed * self.rate).min(self.capacity);
        self.last_update = now;
        
        if self.tokens >= 1.0 {
            self.tokens -= 1.0;
            true
        } else {
            false
        }
    }
}

pub async fn rate_limit_middleware(
    State(limiter): State<Arc<RateLimiter>>,
    request: Request,
    next: Next,
) -> Result<Response, ApiError> {
    let key = if let Some(auth) = request.extensions().get::<AuthContext>() {
        RateLimitKey::Tenant(auth.tenant_id())
    } else {
        let ip = request
            .headers()
            .get("x-forwarded-for")
            .and_then(|h| h.to_str().ok())
            .and_then(|s| s.split(',').next())
            .and_then(|s| s.trim().parse().ok())
            .unwrap_or(IpAddr::V4(Ipv4Addr::UNSPECIFIED));
        
        RateLimitKey::Ip(ip)
    };
    
    if !limiter.check(key) {
        return Err(ApiError::RateLimited);
    }
    
    Ok(next.run(request).await)
}
```

## OpenAPI Generation

```rust
// src/api/openapi.rs

use utoipa::OpenApi;

#[derive(OpenApi)]
#[openapi(
    paths(
        handlers::talent::list_talents,
        handlers::talent::create_talent,
        handlers::talent::get_talent,
        handlers::talent::update_talent,
        handlers::talent::delete_talent,
        handlers::talent::change_talent_status,
        // ... all endpoints
    ),
    components(
        schemas(
            TalentResponse,
            CreateTalentRequest,
            UpdateTalentRequest,
            // ... all schemas
        )
    ),
    tags(
        (name = "talents", description = "Talent management"),
        (name = "campaigns", description = "Campaign management"),
        (name = "contracts", description = "Contract management"),
        (name = "integrations", description = "Platform integrations"),
        (name = "analytics", description = "Analytics and reporting"),
    ),
    info(
        title = "Mox API",
        version = "1.0.0",
        description = "Talent management platform API"
    )
)]
pub struct ApiDoc;

// Serve OpenAPI spec
pub async fn openapi_spec() -> Json<utoipa::openapi::OpenApi> {
    Json(ApiDoc::openapi())
}
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Request latency (p50) | < 5ms |
| Request latency (p99) | < 50ms |
| Write throughput | 10K req/sec |
| Read throughput | 50K req/sec |
| WebSocket connections | 10K concurrent |
| Webhook processing | 1K/sec |

## References

- [Axum Documentation](https://docs.rs/axum/latest/axum/)
- [utoipa OpenAPI](https://docs.rs/utoipa/latest/utoipa/)
- [Tower Middleware](https://docs.rs/tower/latest/tower/)
