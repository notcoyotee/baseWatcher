# Telegram Token Deployment Monitor

There is a telegram channel that posts details of all EVM contracts deployed on the Ethereum L2 chain called Base. This tool scrapes the telegram channel and stores the parsed data into a local db for further analysis. Goal is to catch any non-scammy\unique contracts that are deployed for 💰 🚀 mission. :) 

## Overview

This tool:
- Connects to Telegram using API credentials
- Fetches messages from a specified channel
- Extracts token deployment information
- Stores data in SQLite database
- Handles rate limiting and interruptions
- Optimizes batch processing

## Installation

```pip install -r requirements.txt```

## Configuration

Create `config.env`:

```
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

## Database Schema
### Messages Table
message_id (PRIMARY KEY)
date
token_name
token_symbol
contract_address
deployer_address
deployer_balance
from_address
age
supply
maxtx
maxwallet
tax
similar_tokens
deployed
launched
rugged

### Metadata Table
key (PRIMARY KEY)
value

## Processing Flow
graph TD
    A[Start] --> B[Initialize Database]
    B --> C[Get Last Processed tg message ID]
    C --> D[Fetch Latest Message]
    D --> E[Calculate New Messages]
    E --> F[Process Messages in Batches]
    F --> G{More Messages?}
    G -->|Yes| H[Extract Token Info]
    H --> I[Store in Database]
    I --> J[Update Last Processed ID]
    J --> F
    G -->|No| K[Done]
    F --> L{API Warning?}
    L -->|Yes| M[Wait & Retry]
    M --> F
    L -->|No| G



## Batch Processing
1. Starts from most recent message
2. Processes in reverse chronological order
3. Adapts batch size dynamically based on:
   1. Processing time
   2. API rate limits
   3. Previous successful batch sizes

## Error Handling
 * Handles Telegram API flood warnings
 * Preserves progress on interruption
 * Resumes from last processed message
 * Adapts batch size for optimal performance

## Usage
```python tgExport.py```

Monitor progress in terminal with:
 * Total messages to process
 * Current batch size
 * Processing speed
 * Telegram API status warnings