from telethon import TelegramClient
import asyncio
import sqlite3
from datetime import datetime
import logging
import re
from tqdm import tqdm
import os
from dotenv import load_dotenv

load_dotenv('config.env')
logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
channel_username = 'bananadeployerBASE'

def initialize_database():
    conn = sqlite3.connect('channel_export.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY,
            date TEXT,
            token_name TEXT,
            token_symbol TEXT,
            contract_address TEXT,
            deployer_address TEXT,
            deployer_balance REAL,
            from_address TEXT,
            age TEXT,
            supply TEXT,
            maxtx TEXT,
            maxwallet TEXT,
            tax TEXT,
            similar_tokens TEXT,
            deployed INTEGER,
            launched INTEGER,
            rugged INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('SELECT value FROM metadata WHERE key = "last_processed_message_id"')
    result = cursor.fetchone()
    if not result:
        cursor.execute('''
            INSERT INTO metadata (key, value) 
            VALUES ("last_processed_message_id", "0")
        ''')
        conn.commit()
    
    # Initialize optimal_batch_size if not exists    
    cursor.execute('SELECT value FROM metadata WHERE key = "optimal_batch_size"')
    result = cursor.fetchone()
    if not result:
        cursor.execute('''
            INSERT INTO metadata (key, value) 
            VALUES ("optimal_batch_size", "500")
        ''')
        conn.commit()    
    
    return conn, cursor

def get_db_stats():
    conn = sqlite3.connect('channel_export.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_messages = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT date, token_name 
        FROM messages 
        ORDER BY date DESC 
        LIMIT 1
    ''')
    result = cursor.fetchone()
    last_message_date = result[0] if result else None
    last_token_name = result[1] if result else None
    
    conn.close()
    return total_messages, last_message_date, last_token_name

def get_optimal_batch_size(cursor):
    cursor.execute('SELECT value FROM metadata WHERE key = "optimal_batch_size"')
    result = cursor.fetchone()
    return int(result[0]) if result else 500

def update_optimal_batch_size(cursor, conn, batch_size, processing_time, messages_processed):
    msgs_per_second = messages_processed / processing_time if processing_time > 0 else 0
    
    if msgs_per_second > 0:
        cursor.execute('''
            INSERT OR REPLACE INTO metadata (key, value)
            VALUES ("optimal_batch_size", ?)
        ''', (str(batch_size),))
        conn.commit()

def extract_items(message_text):
    items = {}
    items['Token Name'] = re.search(r'\n(.*?) \(\$', message_text).group(1) if re.search(r'\n(.*?) \(\$', message_text) else 'N/A'
    items['Token Symbol'] = re.search(r'\(\$(.*?)\)', message_text).group(1) if re.search(r'\(\$(.*?)\)', message_text) else 'N/A'
    items['Contract Address'] = re.search(r'`(0x[0-9a-fA-F]{40})`', message_text).group(1) if re.search(r'`(0x[0-9a-fA-F]{40})`', message_text) else 'N/A'
    items['Deployer Address'] = re.search(r'Deployer: \[(0x[0-9a-fA-F]{40})\]', message_text).group(1) if re.search(r'Deployer: \[(0x[0-9a-fA-F]{40})\]', message_text) else 'N/A'
    items['Deployer Balance'] = re.search(r'💰 Balance: ([\d.]+) ETH', message_text).group(1) if re.search(r'💰 Balance: ([\d.]+) ETH', message_text) else 'N/A'
    items['From Address'] = re.search(r'From: \[(0x[0-9a-fA-F]{40})\]', message_text).group(1) if re.search(r'From: \[(0x[0-9a-fA-F]{40})\]', message_text) else 'N/A'
    items['Age'] = re.search(r'Age: (.*?)\n', message_text).group(1) if re.search(r'Age: (.*?)\n', message_text) else 'N/A'
    items['Supply'] = re.search(r'🍌 Supply: ([\d,]+)', message_text).group(1) if re.search(r'🍌 Supply: ([\d,]+)', message_text) else 'N/A'
    items['MaxTx'] = re.search(r'MaxTx: (.*?)\n', message_text).group(1) if re.search(r'MaxTx: (.*?)\n', message_text) else 'N/A'
    items['MaxWallet'] = re.search(r'MaxWallet: (.*?)\n', message_text).group(1) if re.search(r'MaxWallet: (.*?)\n', message_text) else 'N/A'
    items['Tax'] = re.search(r'Tax: (.*?)\n', message_text).group(1) if re.search(r'Tax: (.*?)\n', message_text) else 'N/A'
    items['Similar Tokens'] = re.search(r'⚙️ Similar Tokens: (.*?)\n', message_text).group(1) if re.search(r'⚙️ Similar Tokens: (.*?)\n', message_text) else 'N/A'
    items['Deployed'] = re.search(r'Deployed: (\d+)', message_text).group(1) if re.search(r'Deployed: (\d+)', message_text) else 'N/A'
    items['Launched'] = re.search(r'Launched: (\d+)', message_text).group(1) if re.search(r'Launched: (\d+)', message_text) else 'N/A'
    items['Rugged'] = re.search(r'Rugged: (\d+)', message_text).group(1) if re.search(r'Rugged: (\d+)', message_text) else 'N/A'
    return items

async def export_messages(save_to_db=False):
    client = TelegramClient('session_name', api_id, api_hash)
    await client.start()
    
    channel = await client.get_entity(channel_username)
    last_processed_id = 0
    
    if save_to_db:
        conn, cursor = initialize_database()
        cursor.execute('SELECT value FROM metadata WHERE key = "last_processed_message_id"')
        result = cursor.fetchone()
        last_processed_id = int(result[0]) if result else 0
        batch_size = get_optimal_batch_size(cursor)
        tqdm.write(f"Starting with batch size: {batch_size}")
    else:
        batch_size = 500
    
    try:
        latest_message = await client.get_messages(channel, limit=1)
        start_id = latest_message[0].id if latest_message else 0
        
        total_new_messages = start_id - last_processed_id
        tqdm.write(f"Found {total_new_messages:,} new messages to process")
        
        current_id = start_id
        
        with tqdm(total=total_new_messages, desc="Exporting messages") as pbar:
            while current_id > last_processed_id:
                try:
                    batch_start_time = datetime.now()
                    
                    messages = await client.get_messages(channel, 
                                                       limit=batch_size,
                                                       offset_id=current_id,
                                                       max_id=current_id,
                                                       min_id=last_processed_id)
                    
                    if not messages:
                        break
                        
                    for message in messages:
                        if message.text:
                            items = extract_items(message.text)
                            
                            if save_to_db:
                                cursor.execute('''
                                    INSERT OR IGNORE INTO messages (
                                        message_id, date, token_name, token_symbol, 
                                        contract_address, deployer_address, deployer_balance, 
                                        from_address, age, supply, maxtx, maxwallet, 
                                        tax, similar_tokens, deployed, launched, rugged
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    message.id,
                                    message.date.strftime('%Y-%m-%d %H:%M:%S'),
                                    items['Token Name'], items['Token Symbol'],
                                    items['Contract Address'], items['Deployer Address'],
                                    items['Deployer Balance'], items['From Address'],
                                    items['Age'], items['Supply'], items['MaxTx'],
                                    items['MaxWallet'], items['Tax'],
                                    items['Similar Tokens'], items['Deployed'],
                                    items['Launched'], items['Rugged']
                                ))
                        pbar.update(1)
                    
                    if save_to_db:
                        conn.commit()
                        cursor.execute('''
                            UPDATE metadata 
                            SET value = ? 
                            WHERE key = "last_processed_message_id"
                        ''', (str(messages[-1].id),))
                        conn.commit()

                    batch_time = (datetime.now() - batch_start_time).total_seconds()
                    messages_processed = len(messages)
                    
                    if save_to_db:
                        update_optimal_batch_size(cursor, conn, batch_size, batch_time, messages_processed)
                        
                    if batch_time > 5:
                        batch_size = max(100, batch_size - 50)
                    elif batch_time < 1:
                        batch_size = min(1000, batch_size + 50)
                    
                    pbar.set_postfix(
                        current_id=current_id,
                        batch_size=batch_size,
                        batch_time=f"{batch_time:.1f}s",
                        status="ok"
                    )
                    
                    current_id = messages[-1].id
                    
                except Exception as e:
                    pbar.set_postfix(status=f"Warning: {str(e)}")
                    if hasattr(e, 'seconds'):
                        await asyncio.sleep(e.seconds)
                    continue
                
    except Exception as e:
        logger.error(f"Error: {e}")
        
    finally:
        await client.disconnect()
        if save_to_db:
            conn.close()

if __name__ == '__main__':
    save_to_db = True
    
    try:
        msg_count, last_date, last_token = get_db_stats()
        tqdm.write(f"\nDatabase Status:")
        tqdm.write(f"Total Messages: {msg_count:,}")
        tqdm.write(f"Last Message Date: {last_date}")
        tqdm.write(f"Last Token: {last_token}")
        tqdm.write("-" * 50)
    except sqlite3.OperationalError:
        tqdm.write("\nNo existing database found. Creating new database.")
        tqdm.write("-" * 50)
    
    asyncio.run(export_messages(save_to_db))