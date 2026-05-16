# Gateway Design Decisions

This document explains why each major component exists and what problem it solves.

----

## Gateway responsiblity

The gateway is responsible for moving messages from MQTT to the BLE tag in a reliable and observable way.

Current flow:

MQTT message received
    ↓
Validate payload
    ↓
Store message in SQLite
    ↓
Queue manager processes pending messages
    ↓
BLE client sends payload to tag
    ↓
Tag sends ACK
    ↓
Gateway stores result
    ↓
Gateway publishes ACK back to MQTT

----
                            
## SQLite databse persistence

### What problem does this solve?

The gateway needs memory that survuves crashes, restarts, and temporary offline states.

Without a databse, messages would only live in RAM. if the gateway crahes or restarts, pending messages disappear.

### Why it matters

The database allows the gateway to track:

- received messages
- pending messages
- processing messages
- sent messages
- failed messages
- retry attempts
- BLE results

### Current purpose

SQLite is used as the gateway's local source of truth.

The queue manager should fetch work from the database instead of owining all messages only in memory.

----

## Queue manager

### What problem does this solve?

The gateway should not send every message to the BLE tag immediately as soon as MQTT receives it.

BLE communication is slower and more fragile than MQTT. The tag may be offline, bussy or slow to respond.

### Why it matters

The queue manager controls messages processing order.

It can decide:

- which pending message should be processed next
- when to retry
- when to wait
- when to mark a message as failed
- later, how to avoid sending too many messages to the same tag

### Current purpose

The queue manager separates message receiving from message delivery.

MQTT receives messages.
The queue manager decides whe to process them.

----

## Retry logic

### What problem does this solve?

BLE communication can fail even when the system is mostly working.

The tag may be temporarily un reachable, disconnected, slow to ACK, or outside of range. Without retries, one small BLE failure would
lose the the update.

### Why it matters

Retry logic gives the gateway a controlled way to recover from temporary failures

### Current purpose

The gateway tries to send the payload multiple times before treating the message as failed.

Retries should be tracked so debugging is possible.

----

## Logger

### What problem does this solve?

The gateway has many moving parts:

- MQTT
- validation
- database
- queue manager
- BLE client
- ACK handling

Without logs, its hard to know where a failure happened.

### Why it matters

Logs make the system observable.

The help answer:

- Did MQTT receive the payload?
- Was the payload inserted into the database?
- Did the queue manager process it?
- Did BLE connect?
- Was the payload witten?
- Did the tag send ACK?
- Was the result stored?

### Current purpose

The logger is used for debugging and understanding the full message flow.

----

## Security layer

### Status

Planned later.

### What problem does this solve?

Security protects the system from unaouthorized or modified messages.

Without security, any client that can publish to the broker could potencially send fake updates.

### Possible future responsiblites

Security may include:

- MQTT authentication
- topic permission
- payload validation
- payload signing
- encryption between backend and gateway
- encryption or verification of payloads sent to the tag

### Why it is not added yet

Security should be added after the full flow is understood.

Adding encryption too early can hide basic architecture problems and make debugging harder.

----

## Current design principle

Do not add components just because real systems have them.

Each component must answer:

**What problem does this solve?**

if the answer is unclear, the component is probably mature:

