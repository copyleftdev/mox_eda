# RFC-0006: Network Protocol

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Authors** | Platform Team |
| **Created** | 2024-12-03 |

## Abstract

This RFC defines the binary network protocol for cluster communication (Raft messages) and client-to-cluster communication. The protocol is designed for minimal overhead, checksummed integrity, and efficient batch operations.

## Design Goals

1. **Minimal overhead**: Fixed-size headers, no parsing ambiguity
2. **Checksummed**: Every message verified on receive
3. **Batch-friendly**: Multiple operations per message
4. **Version-aware**: Protocol evolution support
5. **Zero-copy**: Direct buffer access where possible

## Message Format

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           MESSAGE FRAME                                        │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│   0       4       8      12      16      20      24   ...   24+len             │
│  ┌───────┬───────┬───────┬───────┬───────┬───────┬──────────────────┐         │
│  │ Magic │ CRC32 │Version│  Type │ Flags │Length │      Body        │         │
│  │ (u32) │ (u32) │ (u16) │ (u16) │ (u32) │ (u32) │    (bytes)       │         │
│  └───────┴───────┴───────┴───────┴───────┴───────┴──────────────────┘         │
│                                                                                │
│   Magic:   0x4D4F5850 ("MOXP")                                                 │
│   CRC32:   CRC32C of bytes [8..end]                                            │
│   Version: Protocol version (1)                                                │
│   Type:    Message type enum                                                   │
│   Flags:   Compression, encryption, etc.                                       │
│   Length:  Body length in bytes                                                │
│   Body:    Type-specific payload                                               │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Message Types

```rust
// src/network/message.rs

#[repr(u16)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum MessageType {
    // Raft consensus messages
    AppendEntries = 0x0001,
    AppendEntriesResponse = 0x0002,
    RequestVote = 0x0003,
    RequestVoteResponse = 0x0004,
    InstallSnapshot = 0x0005,
    InstallSnapshotResponse = 0x0006,
    
    // View change messages (VR extension)
    StartViewChange = 0x0010,
    DoViewChange = 0x0011,
    StartView = 0x0012,
    
    // Client messages
    ClientRequest = 0x0100,
    ClientResponse = 0x0101,
    ClientRedirect = 0x0102,
    
    // Admin messages
    AddNode = 0x0200,
    RemoveNode = 0x0201,
    ClusterStatus = 0x0202,
    
    // Heartbeat
    Ping = 0x0300,
    Pong = 0x0301,
}

#[repr(u32)]
#[derive(Debug, Clone, Copy)]
pub enum MessageFlags {
    None = 0x0000,
    Compressed = 0x0001,      // Body is LZ4 compressed
    Encrypted = 0x0002,       // Body is encrypted
    Batched = 0x0004,         // Body contains multiple items
    Priority = 0x0008,        // High priority message
}
```

## Raft Messages

```rust
// src/network/raft_messages.rs

/// AppendEntries RPC (leader → followers)
#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct AppendEntriesHeader {
    pub term: u64,
    pub leader_id: u64,
    pub prev_log_index: u64,
    pub prev_log_term: u64,
    pub leader_commit: u64,
    pub entries_count: u32,
    // Followed by: entries_count × Entry
}

#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct Entry {
    pub term: u64,
    pub index: u64,
    pub data_len: u32,
    // Followed by: data_len bytes
}

/// AppendEntries Response
#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct AppendEntriesResponse {
    pub term: u64,
    pub success: u8,
    pub match_index: u64,
    pub conflict_index: u64,   // Optimization: where log diverges
    pub conflict_term: u64,
}

/// RequestVote RPC (candidate → all)
#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct RequestVote {
    pub term: u64,
    pub candidate_id: u64,
    pub last_log_index: u64,
    pub last_log_term: u64,
}

/// RequestVote Response
#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct RequestVoteResponse {
    pub term: u64,
    pub vote_granted: u8,
}

/// InstallSnapshot RPC (leader → lagging follower)
#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct InstallSnapshotHeader {
    pub term: u64,
    pub leader_id: u64,
    pub last_included_index: u64,
    pub last_included_term: u64,
    pub offset: u64,           // Byte offset in snapshot
    pub done: u8,              // Is this the last chunk?
    pub checksum: u64,         // XXHash of complete snapshot
    pub data_len: u32,
    // Followed by: data_len bytes
}
```

## Client Messages

```rust
// src/network/client_messages.rs

/// Client request (client → any node)
#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct ClientRequestHeader {
    pub request_id: u128,      // Client-generated unique ID
    pub tenant_id: u128,       // Tenant UUID
    pub operation: u8,         // Read = 0, Write = 1
    pub consistency: u8,       // Linearizable = 0, Eventual = 1
    pub timeout_ms: u32,
    pub body_len: u32,
    // Followed by: body_len bytes (command or query)
}

/// Client response
#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct ClientResponseHeader {
    pub request_id: u128,
    pub status: u8,            // Success = 0, Error = 1, Redirect = 2
    pub error_code: u16,
    pub body_len: u32,
    // Followed by: body_len bytes (result or error)
}

/// Redirect response (follower → client)
#[derive(Debug, Clone)]
#[repr(C, packed)]
pub struct ClientRedirect {
    pub request_id: u128,
    pub leader_id: u64,
    pub leader_addr_len: u16,
    // Followed by: leader address string
}

#[repr(u8)]
pub enum ClientStatus {
    Success = 0,
    Error = 1,
    Redirect = 2,
    Timeout = 3,
    NotLeader = 4,
    TenantNotFound = 5,
    Unauthorized = 6,
}
```

## Wire Protocol Implementation

```rust
// src/network/protocol.rs

use crc32fast::Hasher;
use std::io::{Read, Write};

const MAGIC: u32 = 0x4D4F5850;
const HEADER_SIZE: usize = 24;
const PROTOCOL_VERSION: u16 = 1;

pub struct WireProtocol;

impl WireProtocol {
    /// Encode message to wire format
    pub fn encode(msg_type: MessageType, flags: u32, body: &[u8]) -> Vec<u8> {
        let total_len = HEADER_SIZE + body.len();
        let mut buffer = Vec::with_capacity(total_len);
        
        // Write header (excluding CRC for now)
        buffer.extend_from_slice(&MAGIC.to_le_bytes());
        buffer.extend_from_slice(&[0u8; 4]); // CRC placeholder
        buffer.extend_from_slice(&PROTOCOL_VERSION.to_le_bytes());
        buffer.extend_from_slice(&(msg_type as u16).to_le_bytes());
        buffer.extend_from_slice(&flags.to_le_bytes());
        buffer.extend_from_slice(&(body.len() as u32).to_le_bytes());
        
        // Write body
        buffer.extend_from_slice(body);
        
        // Calculate CRC over everything after the CRC field
        let crc = crc32fast::hash(&buffer[8..]);
        buffer[4..8].copy_from_slice(&crc.to_le_bytes());
        
        buffer
    }
    
    /// Decode message from wire format
    pub fn decode(buffer: &[u8]) -> Result<Message, ProtocolError> {
        if buffer.len() < HEADER_SIZE {
            return Err(ProtocolError::TooShort);
        }
        
        // Parse header
        let magic = u32::from_le_bytes(buffer[0..4].try_into().unwrap());
        if magic != MAGIC {
            return Err(ProtocolError::InvalidMagic);
        }
        
        let crc = u32::from_le_bytes(buffer[4..8].try_into().unwrap());
        let version = u16::from_le_bytes(buffer[8..10].try_into().unwrap());
        let msg_type = u16::from_le_bytes(buffer[10..12].try_into().unwrap());
        let flags = u32::from_le_bytes(buffer[12..16].try_into().unwrap());
        let body_len = u32::from_le_bytes(buffer[20..24].try_into().unwrap()) as usize;
        
        // Verify version
        if version != PROTOCOL_VERSION {
            return Err(ProtocolError::UnsupportedVersion(version));
        }
        
        // Verify length
        if buffer.len() < HEADER_SIZE + body_len {
            return Err(ProtocolError::IncompleteMessage);
        }
        
        // Verify CRC
        let computed_crc = crc32fast::hash(&buffer[8..HEADER_SIZE + body_len]);
        if crc != computed_crc {
            return Err(ProtocolError::ChecksumMismatch);
        }
        
        // Extract body
        let body = &buffer[HEADER_SIZE..HEADER_SIZE + body_len];
        
        // Decompress if needed
        let body = if flags & MessageFlags::Compressed as u32 != 0 {
            lz4_flex::decompress_size_prepended(body)?
        } else {
            body.to_vec()
        };
        
        // Parse message type
        let msg_type = MessageType::try_from(msg_type)
            .map_err(|_| ProtocolError::UnknownMessageType(msg_type))?;
        
        Ok(Message {
            msg_type,
            flags,
            body,
        })
    }
    
    /// Encode with compression (for large messages)
    pub fn encode_compressed(msg_type: MessageType, body: &[u8]) -> Vec<u8> {
        let compressed = lz4_flex::compress_prepend_size(body);
        
        // Only use compression if it actually helps
        if compressed.len() < body.len() {
            Self::encode(msg_type, MessageFlags::Compressed as u32, &compressed)
        } else {
            Self::encode(msg_type, MessageFlags::None as u32, body)
        }
    }
}

#[derive(Debug)]
pub struct Message {
    pub msg_type: MessageType,
    pub flags: u32,
    pub body: Vec<u8>,
}
```

## Connection Management

```rust
// src/network/connection.rs

use tokio::net::{TcpListener, TcpStream};
use tokio::io::{AsyncReadExt, AsyncWriteExt, BufReader, BufWriter};

pub struct ConnectionManager {
    /// Outbound connection pool
    connections: HashMap<NodeId, ConnectionPool>,
    
    /// Configuration
    config: ConnectionConfig,
}

pub struct ConnectionConfig {
    /// Max connections per peer
    pub max_connections_per_peer: usize,
    
    /// Connection timeout
    pub connect_timeout: Duration,
    
    /// Read timeout
    pub read_timeout: Duration,
    
    /// Write timeout
    pub write_timeout: Duration,
    
    /// Keep-alive interval
    pub keepalive_interval: Duration,
    
    /// Max message size
    pub max_message_size: usize,
}

impl ConnectionManager {
    /// Send message to peer
    pub async fn send(&self, to: NodeId, message: Message) -> Result<()> {
        let conn = self.get_connection(to).await?;
        
        let encoded = WireProtocol::encode(
            message.msg_type,
            message.flags,
            &message.body,
        );
        
        conn.write_all(&encoded).await?;
        conn.flush().await?;
        
        Ok(())
    }
    
    /// Send and wait for response
    pub async fn send_recv(&self, to: NodeId, message: Message) -> Result<Message> {
        let conn = self.get_connection(to).await?;
        
        // Send
        let encoded = WireProtocol::encode(
            message.msg_type,
            message.flags,
            &message.body,
        );
        conn.write_all(&encoded).await?;
        conn.flush().await?;
        
        // Receive response
        let response = self.read_message(&mut conn).await?;
        
        Ok(response)
    }
    
    /// Read a complete message
    async fn read_message(&self, conn: &mut TcpStream) -> Result<Message> {
        // Read header
        let mut header = [0u8; HEADER_SIZE];
        conn.read_exact(&mut header).await?;
        
        // Parse body length
        let body_len = u32::from_le_bytes(header[20..24].try_into().unwrap()) as usize;
        
        if body_len > self.config.max_message_size {
            return Err(ConnectionError::MessageTooLarge);
        }
        
        // Read body
        let mut buffer = vec![0u8; HEADER_SIZE + body_len];
        buffer[..HEADER_SIZE].copy_from_slice(&header);
        conn.read_exact(&mut buffer[HEADER_SIZE..]).await?;
        
        // Decode
        WireProtocol::decode(&buffer)
            .map_err(Into::into)
    }
    
    async fn get_connection(&self, to: NodeId) -> Result<PooledConnection> {
        // Try to get existing connection from pool
        if let Some(pool) = self.connections.get(&to) {
            if let Some(conn) = pool.get() {
                return Ok(conn);
            }
        }
        
        // Create new connection
        let addr = self.resolve_address(to)?;
        let stream = tokio::time::timeout(
            self.config.connect_timeout,
            TcpStream::connect(addr),
        ).await??;
        
        // Configure socket
        stream.set_nodelay(true)?;
        
        // Add to pool
        self.connections
            .entry(to)
            .or_insert_with(|| ConnectionPool::new(self.config.max_connections_per_peer))
            .add(stream.clone());
        
        Ok(PooledConnection::new(stream, to, self.connections.clone()))
    }
}
```

## Batch Operations

```rust
// src/network/batch.rs

/// Batch multiple operations into single message
pub struct BatchBuilder {
    operations: Vec<BatchOperation>,
    max_size: usize,
    current_size: usize,
}

pub struct BatchOperation {
    pub op_type: OperationType,
    pub key: Vec<u8>,
    pub value: Option<Vec<u8>>,
}

impl BatchBuilder {
    pub fn new(max_size: usize) -> Self {
        Self {
            operations: Vec::new(),
            max_size,
            current_size: 0,
        }
    }
    
    pub fn add(&mut self, op: BatchOperation) -> Result<(), BatchFull> {
        let op_size = op.encoded_size();
        
        if self.current_size + op_size > self.max_size {
            return Err(BatchFull);
        }
        
        self.current_size += op_size;
        self.operations.push(op);
        Ok(())
    }
    
    pub fn build(self) -> Vec<u8> {
        let mut buffer = Vec::with_capacity(self.current_size + 4);
        
        // Write operation count
        buffer.extend_from_slice(&(self.operations.len() as u32).to_le_bytes());
        
        // Write each operation
        for op in self.operations {
            buffer.push(op.op_type as u8);
            buffer.extend_from_slice(&(op.key.len() as u16).to_le_bytes());
            buffer.extend_from_slice(&op.key);
            
            if let Some(value) = op.value {
                buffer.extend_from_slice(&(value.len() as u32).to_le_bytes());
                buffer.extend_from_slice(&value);
            } else {
                buffer.extend_from_slice(&0u32.to_le_bytes());
            }
        }
        
        buffer
    }
}
```

## Performance Optimizations

### Zero-Copy Receives

```rust
// src/network/zerocopy.rs

use bytes::{Bytes, BytesMut};

/// Zero-copy message buffer
pub struct MessageBuffer {
    inner: BytesMut,
    read_pos: usize,
}

impl MessageBuffer {
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            inner: BytesMut::with_capacity(capacity),
            read_pos: 0,
        }
    }
    
    /// Try to parse next message without copying
    pub fn try_parse(&mut self) -> Option<MessageRef<'_>> {
        if self.inner.len() - self.read_pos < HEADER_SIZE {
            return None;
        }
        
        let header = &self.inner[self.read_pos..self.read_pos + HEADER_SIZE];
        let body_len = u32::from_le_bytes(header[20..24].try_into().unwrap()) as usize;
        
        if self.inner.len() - self.read_pos < HEADER_SIZE + body_len {
            return None;
        }
        
        let msg_start = self.read_pos;
        let msg_end = self.read_pos + HEADER_SIZE + body_len;
        self.read_pos = msg_end;
        
        Some(MessageRef {
            data: &self.inner[msg_start..msg_end],
        })
    }
    
    /// Compact buffer (remove processed messages)
    pub fn compact(&mut self) {
        if self.read_pos > 0 {
            self.inner.advance(self.read_pos);
            self.read_pos = 0;
        }
    }
}

/// Reference to message in buffer (no copy)
pub struct MessageRef<'a> {
    data: &'a [u8],
}

impl<'a> MessageRef<'a> {
    pub fn msg_type(&self) -> MessageType {
        let type_val = u16::from_le_bytes(self.data[10..12].try_into().unwrap());
        MessageType::try_from(type_val).unwrap()
    }
    
    pub fn body(&self) -> &[u8] {
        &self.data[HEADER_SIZE..]
    }
    
    /// Convert to owned (copies data)
    pub fn to_owned(&self) -> Message {
        WireProtocol::decode(self.data).unwrap()
    }
}
```

## Security (TLS)

```rust
// src/network/tls.rs

use rustls::{ClientConfig, ServerConfig, Certificate, PrivateKey};

pub struct TlsConfig {
    /// Server certificate
    pub cert: Certificate,
    
    /// Private key
    pub key: PrivateKey,
    
    /// CA certificate for peer verification
    pub ca_cert: Certificate,
    
    /// Require client certificates
    pub mutual_tls: bool,
}

impl TlsConfig {
    pub fn server_config(&self) -> Result<ServerConfig> {
        let mut config = ServerConfig::builder()
            .with_safe_defaults()
            .with_client_cert_verifier(if self.mutual_tls {
                Arc::new(AllowAnyAuthenticatedClient::new(self.root_store()?))
            } else {
                NoClientAuth::boxed()
            })
            .with_single_cert(vec![self.cert.clone()], self.key.clone())?;
        
        config.alpn_protocols = vec![b"mox/1".to_vec()];
        
        Ok(config)
    }
    
    pub fn client_config(&self) -> Result<ClientConfig> {
        let mut config = ClientConfig::builder()
            .with_safe_defaults()
            .with_root_certificates(self.root_store()?)
            .with_client_auth_cert(vec![self.cert.clone()], self.key.clone())?;
        
        config.alpn_protocols = vec![b"mox/1".to_vec()];
        
        Ok(config)
    }
}
```

## Metrics

```rust
// src/network/metrics.rs

pub struct NetworkMetrics {
    /// Messages sent by type
    pub messages_sent: Counter,
    
    /// Messages received by type
    pub messages_received: Counter,
    
    /// Bytes sent
    pub bytes_sent: Counter,
    
    /// Bytes received
    pub bytes_received: Counter,
    
    /// Message latency histogram
    pub message_latency: Histogram,
    
    /// Connection count
    pub active_connections: Gauge,
    
    /// Connection errors
    pub connection_errors: Counter,
    
    /// CRC failures
    pub checksum_failures: Counter,
}
```

## References

- [Protocol Buffers Wire Format](https://protobuf.dev/programming-guides/encoding/)
- [Cap'n Proto](https://capnproto.org/)
- [TigerBeetle Network Protocol](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/DESIGN.md#network)
- [LZ4 Compression](https://github.com/lz4/lz4)
