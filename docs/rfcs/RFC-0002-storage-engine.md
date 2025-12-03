# RFC-0002: Storage Engine

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Authors** | Platform Team |
| **Created** | 2024-12-03 |

## Abstract

The storage engine is the foundation of Mox. It provides durable, append-only event storage with checksums, direct I/O via io_uring, and efficient state materialization via an LSM tree.

## Design Goals

1. **Durability**: Never lose committed data
2. **Correctness**: Detect and reject corrupted data
3. **Performance**: Direct I/O, zero-copy, minimal syscalls
4. **Simplicity**: No complex recovery logic

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE ENGINE                                     │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                         WRITE-AHEAD LOG (WAL)                             │ │
│  │                                                                           │ │
│  │   Segment 0        Segment 1        Segment 2        Segment N            │ │
│  │   (sealed)         (sealed)         (sealed)         (active)             │ │
│  │   ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐          │ │
│  │   │ Entry 0 │      │ Entry N │      │ Entry N │      │ Entry N │          │ │
│  │   │ Entry 1 │      │ Entry.. │      │ Entry.. │      │ (writing)│          │ │
│  │   │ ...     │      │ ...     │      │ ...     │      │         │          │ │
│  │   │ Entry N │      │ Entry M │      │ Entry M │      │         │          │ │
│  │   └─────────┘      └─────────┘      └─────────┘      └─────────┘          │ │
│  │                                                                           │ │
│  │   On-disk: events-000000.wal, events-000001.wal, ...                      │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│                                      │ Apply events                             │
│                                      ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                         LSM TREE (Current State)                          │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    MemTable (In-Memory)                         │    │ │
│  │   │   Sorted map of key → value (latest state)                      │    │ │
│  │   │   Size limit: 64MB                                              │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                      │ Flush when full                    │ │
│  │                                      ▼                                    │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    Level 0 (Immutable SSTables)                 │    │ │
│  │   │   SST-0001.sst  SST-0002.sst  SST-0003.sst                      │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                      │ Compaction                         │ │
│  │                                      ▼                                    │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    Level 1+ (Sorted, Non-overlapping)           │    │ │
│  │   │   SST-L1-0001.sst  SST-L1-0002.sst  ...                         │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                         I/O LAYER (io_uring)                              │ │
│  │                                                                           │ │
│  │   • Direct I/O (O_DIRECT) - bypass page cache                             │ │
│  │   • Submission queue → Completion queue                                   │ │
│  │   • Batched syscalls (multiple ops per syscall)                           │ │
│  │   • Zero-copy reads where possible                                        │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Write-Ahead Log (WAL)

### Entry Format

Every entry is self-describing and checksummed:

```
┌────────────────────────────────────────────────────────────────────┐
│                         WAL ENTRY (Variable Size)                  │
├────────────────────────────────────────────────────────────────────┤
│  0       4       8      16      24      32      40    40+len       │
│ ┌───────┬───────┬───────┬───────┬───────┬───────┬──────────────┐  │
│ │ Magic │ CRC32 │ Term  │ Index │ TStamp│Length │    Data      │  │
│ │ (u32) │ (u32) │ (u64) │ (u64) │ (u64) │ (u32) │   (bytes)    │  │
│ └───────┴───────┴───────┴───────┴───────┴───────┴──────────────┘  │
│                                                                    │
│ Magic:  0x4D4F5845 ("MOXE")                                        │
│ CRC32:  CRC32C of bytes [8..end]                                   │
│ Term:   Raft term when entry was created                           │
│ Index:  Monotonically increasing log index                         │
│ TStamp: Nanoseconds since epoch                                    │
│ Length: Length of Data in bytes                                    │
│ Data:   Serialized event (protobuf or msgpack)                     │
└────────────────────────────────────────────────────────────────────┘
```

### Implementation

```rust
// src/storage/wal.rs

use crc32fast::Hasher;
use std::path::PathBuf;

const MAGIC: u32 = 0x4D4F5845;
const HEADER_SIZE: usize = 40;
const SEGMENT_SIZE: usize = 64 * 1024 * 1024; // 64MB

#[repr(C, packed)]
struct EntryHeader {
    magic: u32,
    crc32: u32,
    term: u64,
    index: u64,
    timestamp: u64,
    length: u32,
}

pub struct WriteAheadLog<I: IO> {
    io: I,
    data_dir: PathBuf,
    
    // Current segment
    active_segment: Segment,
    active_segment_id: u64,
    
    // Position tracking
    next_index: u64,
    commit_index: u64,
    
    // Metrics
    entries_written: u64,
    bytes_written: u64,
}

impl<I: IO> WriteAheadLog<I> {
    pub async fn open(io: I, data_dir: PathBuf) -> Result<Self> {
        // Find existing segments
        let segments = Self::discover_segments(&data_dir)?;
        
        // Recover from existing segments
        let (next_index, commit_index) = if segments.is_empty() {
            (1, 0)
        } else {
            Self::recover_state(&io, &segments).await?
        };
        
        // Open or create active segment
        let active_segment_id = segments.last().map(|s| s.id).unwrap_or(0);
        let active_segment = Segment::open_or_create(
            &io,
            &data_dir,
            active_segment_id,
        ).await?;
        
        Ok(Self {
            io,
            data_dir,
            active_segment,
            active_segment_id,
            next_index,
            commit_index,
            entries_written: 0,
            bytes_written: 0,
        })
    }
    
    /// Append entry to log (does NOT fsync)
    pub async fn append(&mut self, term: u64, data: &[u8]) -> Result<LogIndex> {
        let index = self.next_index;
        let timestamp = self.io.now().as_nanos() as u64;
        
        // Build header
        let header = EntryHeader {
            magic: MAGIC,
            crc32: 0, // Filled in below
            term,
            index,
            timestamp,
            length: data.len() as u32,
        };
        
        // Calculate CRC (over term, index, timestamp, length, and data)
        let mut hasher = Hasher::new();
        hasher.update(&term.to_le_bytes());
        hasher.update(&index.to_le_bytes());
        hasher.update(&timestamp.to_le_bytes());
        hasher.update(&(data.len() as u32).to_le_bytes());
        hasher.update(data);
        let crc32 = hasher.finalize();
        
        // Write entry
        let mut entry = Vec::with_capacity(HEADER_SIZE + data.len());
        entry.extend_from_slice(&header.magic.to_le_bytes());
        entry.extend_from_slice(&crc32.to_le_bytes());
        entry.extend_from_slice(&header.term.to_le_bytes());
        entry.extend_from_slice(&header.index.to_le_bytes());
        entry.extend_from_slice(&header.timestamp.to_le_bytes());
        entry.extend_from_slice(&header.length.to_le_bytes());
        entry.extend_from_slice(data);
        
        // Check if we need a new segment
        if self.active_segment.size() + entry.len() > SEGMENT_SIZE {
            self.rotate_segment().await?;
        }
        
        // Append to active segment
        self.active_segment.append(&entry).await?;
        
        self.next_index += 1;
        self.entries_written += 1;
        self.bytes_written += entry.len() as u64;
        
        Ok(LogIndex(index))
    }
    
    /// Sync all pending writes to disk
    pub async fn sync(&mut self) -> Result<()> {
        self.active_segment.sync().await
    }
    
    /// Read entry by index
    pub async fn read(&self, index: LogIndex) -> Result<Option<LogEntry>> {
        let segment_id = self.segment_for_index(index);
        let segment = self.open_segment(segment_id).await?;
        
        let entry = segment.read_entry(index).await?;
        
        // Verify checksum
        if let Some(ref e) = entry {
            self.verify_checksum(e)?;
        }
        
        Ok(entry)
    }
    
    /// Read range of entries (for replication)
    pub async fn read_range(
        &self,
        start: LogIndex,
        end: LogIndex,
    ) -> Result<Vec<LogEntry>> {
        let mut entries = Vec::with_capacity((end.0 - start.0) as usize);
        
        for index in start.0..end.0 {
            if let Some(entry) = self.read(LogIndex(index)).await? {
                entries.push(entry);
            }
        }
        
        Ok(entries)
    }
    
    fn verify_checksum(&self, entry: &LogEntry) -> Result<()> {
        let mut hasher = Hasher::new();
        hasher.update(&entry.term.to_le_bytes());
        hasher.update(&entry.index.0.to_le_bytes());
        hasher.update(&entry.timestamp.to_le_bytes());
        hasher.update(&(entry.data.len() as u32).to_le_bytes());
        hasher.update(&entry.data);
        
        let computed = hasher.finalize();
        
        if computed != entry.crc32 {
            return Err(StorageError::ChecksumMismatch {
                index: entry.index,
                expected: entry.crc32,
                computed,
            });
        }
        
        Ok(())
    }
    
    async fn rotate_segment(&mut self) -> Result<()> {
        // Seal current segment
        self.active_segment.seal().await?;
        
        // Create new segment
        self.active_segment_id += 1;
        self.active_segment = Segment::create(
            &self.io,
            &self.data_dir,
            self.active_segment_id,
        ).await?;
        
        Ok(())
    }
}
```

## io_uring Integration

```rust
// src/io/uring.rs

use io_uring::{opcode, types, IoUring, SubmissionQueue, CompletionQueue};
use std::os::unix::io::AsRawFd;

pub struct UringIO {
    ring: IoUring,
    pending: HashMap<u64, PendingOp>,
    next_user_data: u64,
}

impl UringIO {
    pub fn new(queue_depth: u32) -> Result<Self> {
        let ring = IoUring::builder()
            .setup_sqpoll(1000)  // 1ms idle before kernel thread sleeps
            .build(queue_depth)?;
        
        Ok(Self {
            ring,
            pending: HashMap::new(),
            next_user_data: 0,
        })
    }
    
    /// Submit a write operation
    pub async fn write(
        &mut self,
        fd: &File,
        offset: u64,
        data: &[u8],
    ) -> Result<usize> {
        let user_data = self.next_user_data;
        self.next_user_data += 1;
        
        // Build write operation
        let write_op = opcode::Write::new(
            types::Fd(fd.as_raw_fd()),
            data.as_ptr(),
            data.len() as u32,
        )
        .offset(offset)
        .build()
        .user_data(user_data);
        
        // Submit
        unsafe {
            self.ring.submission().push(&write_op)?;
        }
        self.ring.submit()?;
        
        // Wait for completion
        let cqe = self.ring.completion().next().unwrap();
        
        if cqe.result() < 0 {
            return Err(io::Error::from_raw_os_error(-cqe.result()).into());
        }
        
        Ok(cqe.result() as usize)
    }
    
    /// Submit a read operation
    pub async fn read(
        &mut self,
        fd: &File,
        offset: u64,
        len: usize,
    ) -> Result<Vec<u8>> {
        let mut buffer = vec![0u8; len];
        let user_data = self.next_user_data;
        self.next_user_data += 1;
        
        // Build read operation
        let read_op = opcode::Read::new(
            types::Fd(fd.as_raw_fd()),
            buffer.as_mut_ptr(),
            len as u32,
        )
        .offset(offset)
        .build()
        .user_data(user_data);
        
        // Submit
        unsafe {
            self.ring.submission().push(&read_op)?;
        }
        self.ring.submit()?;
        
        // Wait for completion
        let cqe = self.ring.completion().next().unwrap();
        
        if cqe.result() < 0 {
            return Err(io::Error::from_raw_os_error(-cqe.result()).into());
        }
        
        buffer.truncate(cqe.result() as usize);
        Ok(buffer)
    }
    
    /// Fsync a file
    pub async fn fsync(&mut self, fd: &File) -> Result<()> {
        let user_data = self.next_user_data;
        self.next_user_data += 1;
        
        let fsync_op = opcode::Fsync::new(types::Fd(fd.as_raw_fd()))
            .build()
            .user_data(user_data);
        
        unsafe {
            self.ring.submission().push(&fsync_op)?;
        }
        self.ring.submit_and_wait(1)?;
        
        let cqe = self.ring.completion().next().unwrap();
        
        if cqe.result() < 0 {
            return Err(io::Error::from_raw_os_error(-cqe.result()).into());
        }
        
        Ok(())
    }
    
    /// Batch multiple operations
    pub async fn batch(&mut self, ops: Vec<BatchOp>) -> Result<Vec<BatchResult>> {
        let mut results = Vec::with_capacity(ops.len());
        let start_user_data = self.next_user_data;
        
        // Submit all operations
        for (i, op) in ops.iter().enumerate() {
            let user_data = start_user_data + i as u64;
            
            let sqe = match op {
                BatchOp::Write { fd, offset, data } => {
                    opcode::Write::new(
                        types::Fd(fd.as_raw_fd()),
                        data.as_ptr(),
                        data.len() as u32,
                    )
                    .offset(*offset)
                    .build()
                    .user_data(user_data)
                }
                BatchOp::Fsync { fd } => {
                    opcode::Fsync::new(types::Fd(fd.as_raw_fd()))
                        .build()
                        .user_data(user_data)
                }
            };
            
            unsafe {
                self.ring.submission().push(&sqe)?;
            }
        }
        
        self.next_user_data += ops.len() as u64;
        
        // Submit and wait for all completions
        self.ring.submit_and_wait(ops.len())?;
        
        // Collect results
        for _ in 0..ops.len() {
            let cqe = self.ring.completion().next().unwrap();
            results.push(BatchResult {
                user_data: cqe.user_data(),
                result: cqe.result(),
            });
        }
        
        Ok(results)
    }
}
```

## LSM Tree for State

```rust
// src/storage/lsm.rs

use std::collections::BTreeMap;
use parking_lot::RwLock;

pub struct LsmTree<I: IO> {
    io: I,
    data_dir: PathBuf,
    
    // In-memory components
    active_memtable: RwLock<MemTable>,
    immutable_memtables: RwLock<Vec<Arc<MemTable>>>,
    
    // On-disk components
    levels: Vec<Level>,
    
    // Configuration
    memtable_size_limit: usize,
    level_size_multiplier: usize,
}

struct MemTable {
    data: BTreeMap<Vec<u8>, Value>,
    size: usize,
}

enum Value {
    Put(Vec<u8>),
    Delete,
}

impl<I: IO> LsmTree<I> {
    /// Put a key-value pair
    pub fn put(&self, key: &[u8], value: &[u8]) -> Result<()> {
        let mut memtable = self.active_memtable.write();
        
        let entry_size = key.len() + value.len() + 16; // overhead
        memtable.data.insert(key.to_vec(), Value::Put(value.to_vec()));
        memtable.size += entry_size;
        
        // Check if memtable is full
        if memtable.size >= self.memtable_size_limit {
            drop(memtable);
            self.rotate_memtable()?;
        }
        
        Ok(())
    }
    
    /// Get a value by key
    pub fn get(&self, key: &[u8]) -> Result<Option<Vec<u8>>> {
        // Check active memtable
        {
            let memtable = self.active_memtable.read();
            if let Some(value) = memtable.data.get(key) {
                return match value {
                    Value::Put(v) => Ok(Some(v.clone())),
                    Value::Delete => Ok(None),
                };
            }
        }
        
        // Check immutable memtables (newest first)
        {
            let immutables = self.immutable_memtables.read();
            for memtable in immutables.iter().rev() {
                if let Some(value) = memtable.data.get(key) {
                    return match value {
                        Value::Put(v) => Ok(Some(v.clone())),
                        Value::Delete => Ok(None),
                    };
                }
            }
        }
        
        // Check on-disk levels (L0 first, then L1, L2, ...)
        for level in &self.levels {
            if let Some(value) = level.get(key).await? {
                return Ok(Some(value));
            }
        }
        
        Ok(None)
    }
    
    /// Delete a key
    pub fn delete(&self, key: &[u8]) -> Result<()> {
        let mut memtable = self.active_memtable.write();
        memtable.data.insert(key.to_vec(), Value::Delete);
        memtable.size += key.len() + 8;
        Ok(())
    }
    
    /// Range scan
    pub fn scan(
        &self,
        start: &[u8],
        end: &[u8],
        limit: usize,
    ) -> Result<Vec<(Vec<u8>, Vec<u8>)>> {
        // Merge iterators from all sources
        let mut heap = BinaryHeap::new();
        
        // Add memtable iterators
        // Add SSTable iterators
        // Merge and deduplicate
        
        let mut results = Vec::with_capacity(limit);
        while results.len() < limit {
            if let Some(entry) = heap.pop() {
                if entry.key >= start && entry.key < end {
                    if let Value::Put(v) = entry.value {
                        results.push((entry.key, v));
                    }
                }
            } else {
                break;
            }
        }
        
        Ok(results)
    }
    
    fn rotate_memtable(&self) -> Result<()> {
        let old_memtable = {
            let mut active = self.active_memtable.write();
            std::mem::replace(&mut *active, MemTable::new())
        };
        
        // Add to immutable list
        {
            let mut immutables = self.immutable_memtables.write();
            immutables.push(Arc::new(old_memtable));
        }
        
        // Trigger background flush
        self.schedule_flush();
        
        Ok(())
    }
}
```

## File Layout

```
/var/lib/mox/
├── wal/
│   ├── events-000000.wal     # Sealed segment
│   ├── events-000001.wal     # Sealed segment
│   └── events-000002.wal     # Active segment
│
├── state/
│   ├── CURRENT               # Current manifest
│   ├── MANIFEST-000001       # SSTable manifest
│   ├── L0/
│   │   ├── 000001.sst
│   │   └── 000002.sst
│   ├── L1/
│   │   ├── 000003.sst
│   │   └── 000004.sst
│   └── L2/
│       └── 000005.sst
│
├── snapshots/
│   ├── snapshot-000001.snap  # Full state snapshot
│   └── snapshot-000002.snap
│
└── meta/
    ├── node.id               # Node identifier
    ├── cluster.conf          # Cluster configuration
    └── vote.state            # Raft vote state
```

## Checksumming Strategy

| Data | Algorithm | When Verified |
|------|-----------|---------------|
| WAL entries | CRC32C | Every read |
| SSTable blocks | CRC32C | Every read |
| Snapshots | XXHash64 | On load |
| Network messages | CRC32C | On receive |

## Performance Characteristics

| Operation | Time Complexity | I/O Operations |
|-----------|-----------------|----------------|
| Write (append) | O(1) | 1 write + 1 fsync |
| Read (by index) | O(1) | 1 read |
| Read (by key) | O(log N) | 0-L reads |
| Scan (range) | O(K log N) | Multiple reads |
| Compaction | O(N) | Many reads + writes |

## References

- [TigerBeetle Storage](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/DESIGN.md#storage)
- [RocksDB Architecture](https://github.com/facebook/rocksdb/wiki/RocksDB-Overview)
- [io_uring Documentation](https://kernel.dk/io_uring.pdf)
- [CRC32C Hardware Acceleration](https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html#text=crc32)
