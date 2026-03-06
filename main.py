
from typing import Union
import configparser

from fastapi import FastAPI, HTTPException, Request, Form, File, UploadFile, Depends
from fastapi.security import APIKeyHeader
from pathlib import Path
from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient, DataType
from pydantic import BaseModel
import pandas as pd
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import pandas as pd
import json
import re
import asyncio
import functools
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

cfp = configparser.RawConfigParser()
cfp.read('config.ini')
milvus_uri = cfp.get('example', 'uri')
token = cfp.get('example', 'token')

import os

MILVUS_URI = os.environ.get("MILVUS_URI", "http://127.0.0.1:19530")
MILVUS_TOKEN = os.environ.get("MILVUS_TOKEN", None)
MILVUS_DATA_DIR = os.environ.get("MILVUS_DATA_DIR", None)

# Initialize client based on configuration
milvus_uri = os.environ.get("MILVUS_URI", "")

if milvus_uri == "milvus.db" or milvus_uri.endswith(".db"):
    # Milvus Lite - file-based
    client = MilvusClient(data_dir="./data")
elif MILVUS_DATA_DIR:
    # Milvus Lite - file-based with explicit data_dir
    client = MilvusClient(data_dir=MILVUS_DATA_DIR)
elif MILVUS_TOKEN:
    # Zilliz Cloud or remote Milvus with token
    client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)
else:
    # Local Milvus server
    client = MilvusClient(uri=MILVUS_URI, user="root", password="Milvus")

USER = "root"
PASSWORD = "Milvus"
COLLECTION_NAME = "transactions_vectors"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSION = 384 # Dimension of the 'all-MiniLM-L6-v2' model outputs
MODEL_KWARGS = {"dtype": "float16"}

CATEGORY_KEYWORDS = {
    "Shopping": ["shopping", "shop", "purchase", "bought", "amazon", "apple"],
    "Groceries": ["grocery", "groceries", "vegetables", "supermarket", "whole foods"],
    "Food & Dining": ["food", "dining", "restaurant", "coffee", "starbucks", "mcdonald"],
    "Transportation": ["transportation", "transport",   "taxi", "uber", "ola", "cab", "bus", "train"],
    "Entertainment": ["movie", "netflix", "concert", "game"],
    "Utilities": ["electricity", "water", "gas bill", "internet", "wifi", "broadband"],
    "Gas": ["gas", "fuel", "petrol", "diesel", "lpg", "cng", "refill", "cylinder"],
}

CATEGORY_PRIORITY = [
    "Utilities",
    "Gas",
    "Transportation",
    "Food & Dining",
    "Groceries",
    "Shopping",
    "Entertainment",
]

def detect_category_by_keywords(query: str):
    q = query.lower()

    for category in CATEGORY_PRIORITY:
        for kw in CATEGORY_KEYWORDS.get(category, []):
            if kw in q:
                return category

    return None

# 1. Create a Pydantic model to define the expected data structure
class Item(BaseModel):
    name: str
    price: float
    is_offer: bool | None = None  # Optional field

app = FastAPI()
model = SentenceTransformer(EMBEDDING_MODEL_NAME, MODEL_KWARGS)

# API Key header for authentication
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Helper function to run synchronous Milvus operations asynchronously in FastAPI
def make_async(func):
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return async_wrapper

async_search = make_async(client.search)

def split_category_and_amount(response):
    query = response.get("query", "")

    results = []
    for match in response.get("matches", []):
        text = match.get("text", "")

        # Expected format:
        # "Month, Year - Merchant - Category - Amount"
        #text, year, month, category
        parts = [p.strip() for p in text.split(" - ")]

        if len(parts) == 4:
            date, merchant, category, amount = parts
            results.append({
                "date": date,
                "merchant": merchant,
                "category": category,
                "amount": float(amount)
            })

    return query, results

def calculate_total_amount(data):
    return round(sum(item.get("totalAmount", 0) for item in data), 2)

def to_google_data_table(data):
    table = [["Name", "Amount"]]
    for item in data:
        table.append([item["name"], item["totalAmount"]])
    return table

def normalize(text):
    return re.sub(r"[^a-z\s]", "", text.lower())

def find_matched_categories(data):
    search_str = str(data[0])
    search_words = normalize(search_str).split()

    matched = {
        item["category"]
        for item in data[1]
        if any(
            word in search_words
            for word in normalize(item["category"]).split()
        )
    }

    category = next(iter(matched))

    return category


def group_categories(data, category):
    matched_categories = category

    print("matched_categories:", matched_categories)
    if not matched_categories:
        # If no category specified, include all results
        matched_categories = set()
    elif isinstance(matched_categories, str):
        matched_categories = {matched_categories}

    matched_categories = {c.lower().strip() for c in matched_categories}

    grouped = {}

    for item in data[1]:
        item_category = item["category"].lower().strip()
        # Include all items if no category filter specified
        if not matched_categories or any(cat in item_category for cat in matched_categories):
            name = item["merchant"]
            category = item["category"]

            if name not in grouped:
                grouped[name] = {
                    "name": name,
                    "category": category,
                    "totalAmount": 0.0,
                    "count": 0
                }

            grouped[name]["totalAmount"] += item["amount"]
            grouped[name]["count"] += 1

    return grouped

def grouped_to_array(grouped):
    return [
        {
            "name": item["name"],
            "category": item["category"],
            "totalAmount": round(item["totalAmount"], 2),
            "transactions": item["count"]
        }
        for item in grouped.values()
    ]

def highest_spend(data):
    if not data:
        return None

    item = max(data, key=lambda x: x.get("totalAmount", 0))
    return {
        "name": item.get("name"),
        "amount": round(item.get("totalAmount", 0), 2)
    }

def parse_query_date(query: str):
    query = query.lower()
    now = datetime.now()

    month_map = {
        "january": "January", "february": "February", "march": "March",
        "april": "April", "may": "May", "june": "June",
        "july": "July", "august": "August", "september": "September",
        "october": "October", "november": "November", "december": "December"
    }

    year = None
    month = None

    for m in month_map:
        if m in query:
            month = month_map[m]
            break

    year_match = re.search(r"\b(20\d{2})\b", query)
    if year_match:
        year = int(year_match.group())

    return year, month

def extract_date_range(query: str, now=None):
    """
    Returns (start_date, end_date) or (None, None)
    """
    q = query.lower()
    now = now or datetime.now()

    # ---------------- LAST N DAYS ----------------
    m = re.search(r"last\s+(\d+)\s+days", q)
    if m:
        days = int(m.group(1))
        return now - timedelta(days=days), now

    # ---------------- LAST WEEK ----------------
    if "last week" in q:
        # previous full week (Mon–Sun)
        end = now - timedelta(days=now.weekday() + 1)
        start = end - timedelta(days=6)
        return start, end

    # ---------------- LAST MONTH ----------------
    if "last month" in q:
        first_this_month = now.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        start = last_month_end.replace(day=1)
        return start, last_month_end

    # ---------------- LAST YEAR ----------------
    if "last year" in q:
        start = now.replace(year=now.year - 1, month=1, day=1)
        end = now.replace(year=now.year - 1, month=12, day=31)
        return start, end

    return None, None


def month_name(dt):
    return dt.strftime("%B")

def build_date_expr(start: datetime, end: datetime):
    exprs = []
    cursor = start.replace(day=1)

    while cursor <= end:
        year = cursor.year
        month = month_name(cursor)

        if year == start.year and month == month_name(start):
            exprs.append(
                f"year == {year} && month == '{month}' && day >= {start.day}"
            )
        elif year == end.year and month == month_name(end):
            exprs.append(
                f"year == {year} && month == '{month}' && day <= {end.day}"
            )
        else:
            exprs.append(
                f"year == {year} && month == '{month}'"
            )

        cursor += relativedelta(months=1)

    return " || ".join(exprs)

def strict_category_match(row_category: str, chosen_category: str) -> bool:
    if not row_category or not chosen_category:
        return False

    # Split compound categories like "Gas & Transportation"
    parts = [p.strip().lower() for p in row_category.split("&")]

    # Match only exact category token
    return chosen_category.lower() == row_category.strip().lower()



async def filter_query_process_data(search_str: str, api_key: str = None):
    """Performs a semantic search for the query and returns similar texts."""
    # Determine collection name based on API key
    if api_key:
        collection_name = f"transactions_{api_key[:16]}"
    else:
        collection_name = COLLECTION_NAME

    # Check if collection exists
    if not client.has_collection(collection_name):
        return [], None

    try:
        # 🔍 Step 1: Parse date info
        start, end = extract_date_range(search_str)

        if start:
            date_expr = build_date_expr(start, end)
        else:
            date_expr = None
            year, month = parse_query_date(search_str)

        # 🔍 Step 2: Create embedding
        query_vec = model.encode([search_str], normalize_embeddings=True).tolist()[0]

        # 🔍 Step 3: Build Milvus filter
        category = detect_category_by_keywords(search_str)

        filters = []
        if date_expr:
            filters.append(date_expr)
        else :
            if year:
                filters.append(f"year == {year}")
            if month:
                filters.append(f"month == '{month}'")

        if category:
            filters.append(f"category LIKE '%{category}%'")

        filter_expr = " && ".join(filters) if filters else None

        print(f"Filter expression: {filter_expr}")

        # 🔍 Step 4: Hybrid search
        try:
            results = await async_search(
                collection_name=collection_name,
                data=[query_vec],
                filter=filter_expr,
                output_fields=["text", "year", "month", "category"],
                limit=100
            )
            print(f"Search results: {results}")
        except Exception as search_err:
            print(f"Search error: {search_err}")
            # Try without filter if filter causes issue
            if filter_expr:
                results = await async_search(
                    collection_name=collection_name,
                    data=[query_vec],
                    output_fields=["text", "year", "month", "category"],
                    limit=100
                )
            else:
                raise search_err


        matches = []
        # Check if results exist and are not empty
        if results and results[0]:
            for hit in results[0]:  # search returns list of lists
                entity = hit.get("entity", {})
                matches.append({
                    "text": entity.get("text"),
                    "year": entity.get("year"),
                    "month": entity.get("month"),
                    "category": entity.get("category"),
                    "id": hit.get("id")
                })

        parsedData = split_category_and_amount({
            "query": search_str,
            "matches": matches
        })

        return parsedData, category

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Endpoint to receive the form data
@app.post("/result")
async def process_data(request: Request, user_input: str = Form(...)):
    # The data from the form fields is automatically extracted by FastAPI's Form(...)
    """Performs a semantic search for the query and returns similar texts."""
    try:

        parsedData, category = await filter_query_process_data(user_input)

        print("-------------------- PARSED DATA --------------------")
        print(parsedData)

        grouped = group_categories(parsedData, category)

        grouped_array = grouped_to_array(grouped)
        highest = highest_spend(grouped_array)

        total = calculate_total_amount(grouped_array)
        chart_data = to_google_data_table(grouped_array)

        return templates.TemplateResponse(
            name="results.html",
            context={"request": request, "total": total, "chart_data": json.dumps(chart_data) ,
            "query":parsedData[0],
            "category": normalize(category) if category else "All",
            "highest": highest }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse(
        name="index.html",
        context={"request": request, "title": "Standard Example", "content": "This is standard content."}
    )


# SearchRequest model
class SearchRequest(BaseModel):
    query: str
    limit: int = 20


# API Endpoints for frontend
@app.post("/api/search")
async def api_search(request: SearchRequest, api_key: str = Depends(API_KEY_HEADER)):
    try:
        parsedData, category = await filter_query_process_data(request.query, api_key)
        grouped = group_categories(parsedData, category)
        grouped_array = grouped_to_array(grouped)

        # Get raw transaction data for dates
        raw_transactions = parsedData[1] if len(parsedData) > 1 else []

        # Convert to format expected by frontend: merchant, category, amount, month, day, year
        transactions = []
        for idx, item in enumerate(grouped_array[:request.limit]):
            # Get date from raw data
            txn = raw_transactions[idx] if idx < len(raw_transactions) else {}
            date_str = txn.get("date", "")

            # Parse date like "29, November, 2024"
            day = ""
            month = ""
            year = None
            if date_str:
                parts = [p.strip() for p in date_str.split(",")]
                if len(parts) >= 3:
                    day = parts[0]
                    month = parts[1]
                    year = parts[2]

            transactions.append({
                "merchant": item["name"],
                "category": item["category"],
                "amount": item["totalAmount"],
                "month": month,
                "day": day,
                "year": year
            })

        return {
            "results": transactions,
            "query": request.query
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/summary")
async def api_summary(api_key: str = Depends(API_KEY_HEADER)):
    try:
        # Get all transactions
        parsedData, _ = await filter_query_process_data("all", api_key)
        grouped = group_categories(parsedData, None)
        grouped_array = grouped_to_array(grouped)

        total_spending = sum(item["totalAmount"] for item in grouped_array)
        transaction_count = sum(item["transactions"] for item in grouped_array)

        by_category = {}
        by_merchant = []
        for item in grouped_array:
            cat = item["category"]
            if cat not in by_category:
                by_category[cat] = 0
            by_category[cat] += item["totalAmount"]
            by_merchant.append({"merchant": item["name"], "amount": item["totalAmount"]})

        by_merchant.sort(key=lambda x: x["amount"], reverse=True)

        return {
            "total_spending": total_spending,
            "transaction_count": transaction_count,
            "by_category": by_category,
            "by_merchant": by_merchant
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/categories")
async def api_categories():
    try:
        return {"categories": list(CATEGORY_KEYWORDS.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transactions")
async def api_transactions(
    limit: int = 100,
    category: str = None,
    year: int = None,
    api_key: str = Depends(API_KEY_HEADER),
):
    try:
        query = "all"
        if category:
            query = category
        if year:
            query += f" {year}"

        parsedData, detected_category = await filter_query_process_data(query, api_key)
        grouped = group_categories(parsedData, category)
        grouped_array = grouped_to_array(grouped)

        # Convert to transaction format
        transactions = []
        for item in grouped_array:
            transactions.append({
                "merchant": item["name"],
                "category": item["category"],
                "amount": item["totalAmount"],
                "count": item["transactions"]
            })

        return {"results": transactions[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint to receive the form data
@app.post("/search")
async def process_data(request: Request, search_str: str = Form(...)):
    try:
        parsedData, category = await filter_query_process_data(search_str)

        grouped = group_categories(parsedData, category)
        print("-------------------- PARSED DATA --------------------")
        print(grouped)
        grouped_array = grouped_to_array(grouped)

        return grouped_array

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Data Ingestion Endpoints
# ============================================

# Ingest response model
class IngestResponse(BaseModel):
    status: str
    records_processed: int
    records_inserted: int
    collection: str


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    api_key: str = Depends(API_KEY_HEADER),
    clear_existing: str = "true",
):
    """Ingest transaction data from file upload."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    # Convert string to boolean
    clear_existing_bool = clear_existing.lower() == "true"

    # Save uploaded file temporarily
    temp_path = Path("temp") / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Write uploaded file
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        # Load and process data
        df = pd.read_csv(temp_path)
        records = process_csv_data(df)

        # Generate embeddings
        texts = [r["text"] for r in records]
        embeddings = model.encode(texts, normalize_embeddings=True)
        for i, emb in enumerate(embeddings):
            records[i]["embedding"] = emb.tolist()

        # Create collection if needed
        collection_name = f"transactions_{api_key[:16]}"
        if clear_existing_bool and client.has_collection(collection_name):
            client.drop_collection(collection_name)

        if not client.has_collection(collection_name):
            # Create schema
            schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
            schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
            schema.add_field("text", DataType.VARCHAR, max_length=500)
            schema.add_field("year", DataType.INT64)
            schema.add_field("month", DataType.VARCHAR, max_length=20)
            schema.add_field("day", DataType.INT64)
            schema.add_field("merchant", DataType.VARCHAR, max_length=200)
            schema.add_field("category", DataType.VARCHAR, max_length=100)
            schema.add_field("amount", DataType.FLOAT)
            schema.add_field("description", DataType.VARCHAR, max_length=500)
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=384)

            # Create index
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="embedding",
                index_type="AUTOINDEX",
                metric_type="COSINE",
            )

            client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params,
            )

        # Insert data
        client.load_collection(collection_name)
        inserted_ids = client.insert(collection_name=collection_name, data=records)

        return IngestResponse(
            status="success",
            records_processed=len(records),
            records_inserted=len(inserted_ids),
            collection=collection_name,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_path.exists():
            temp_path.unlink()


def process_csv_data(df: pd.DataFrame) -> list[dict]:
    """Process CSV DataFrame into transaction records."""
    # Map columns
    column_mapping = {
        "date": ["Date", "date", "Transaction Date", "trans_date"],
        "merchant": ["Merchant_Name", "merchant", "Merchant", "Description", "description"],
        "category": ["Category", "category", "Type", "type"],
        "amount": ["Amount", "amount", "Value", "value", "Debit", "debit"],
    }

    new_columns = {}
    for std_name, possible_names in column_mapping.items():
        for col in df.columns:
            if col in possible_names:
                new_columns[col] = std_name
                break

    df = df.rename(columns=new_columns)

    records = []
    for _, row in df.iterrows():
        date_str = str(row.get("date", ""))
        year, month, day = None, None, None

        # Parse date
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                year = dt.year
                month = dt.strftime("%B")
                day = dt.day
                break
            except:
                continue

        merchant = str(row.get("merchant", ""))
        category = str(row.get("category", ""))
        amount = float(row.get("amount", 0))

        # Auto-detect category if "Other" or empty
        if not category or category.lower() == "other":
            category = detect_category_by_keywords(merchant) or "Other"

        text = f"{month}, {year} - {merchant} - {category} - {amount}"

        records.append({
            "text": text,
            "year": year,
            "month": month,
            "day": day,
            "merchant": merchant,
            "category": category,
            "amount": amount,
            "description": merchant,
        })

    return records


@app.get("/api/ingest/status")
async def get_ingest_status(api_key: str = Depends(API_KEY_HEADER)):
    """Get ingestion status."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    collection_name = f"transactions_{api_key[:16]}"
    if not client.has_collection(collection_name):
        return {"status": "not_initialized", "record_count": 0}

    stats = client.get_collection_stats(collection_name)
    return {
        "status": "ready",
        "record_count": stats.get("row_count", 0),
        "collection": collection_name,
    }
