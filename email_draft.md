Subject: SAI - Transaction Search AI - Technical Overview & Investment Opportunity

---

Dear [Seed Funder Name],

Thank you for your interest in SAI (Transaction Search AI). I'm excited to share a comprehensive overview of our technology, how it works, and its security architecture.

---

## What is SAI?

SAI is an intelligent transaction search platform that allows users to search through their financial transactions using natural language queries. Instead of filtering through spreadsheets or complex search parameters, users can simply ask questions like:

- "How much did I spend on shopping last month?"
- "What were my dining expenses this year?"
- "Show me all Uber rides"

The system understands the intent behind these queries and returns relevant results instantly.

---

## How It Works

### 1. **Data Ingestion**
- Users upload their transaction data via CSV, Excel, or JSON files
- The system automatically normalizes data (handles different column names like "Date"/"Transaction Date"/"trans_date")
- Auto-categorization: Merchant names are analyzed using keyword matching to assign categories (Shopping, Groceries, Food & Dining, Transportation, Entertainment, Utilities, Gas, Healthcare)

### 2. **Vector Embedding**
- Each transaction is converted into a numerical "embedding" using the **all-MiniLM-L6-v2** sentence transformer model
- This converts text like "November, 2024 - Zara - Shopping - $198.45" into a 384-dimensional vector
- Similar transactions have vectors close to each other in mathematical space

### 3. **Vector Database Storage (Milvus)**
- All embeddings are stored in **Milvus**, an open-source vector database
- Currently running on a local Milvus server at `http://127.0.0.1:19530`
- Can be easily deployed to **Zilliz Cloud** (managed Milvus) for scalability
- Schema includes: `text`, `year`, `month`, `day`, `merchant`, `category`, `amount`, `description`, `embedding`

### 4. **Semantic Search**
- When user enters a query, it gets converted to a vector using the same embedding model
- Milvus performs **similarity search** to find the closest matching transactions
- Results are ranked by relevance (cosine similarity)
- Filters can be applied for date ranges, categories, etc.

---

## Data Input Options

### Option 1: File Upload (CSV, Excel, JSON)
Users can directly upload their transaction files in various formats:
- **CSV** - Standard comma-separated values
- **Excel** - .xlsx and .xls files
- **JSON** - JavaScript Object Notation

The system automatically detects and normalizes columns:
- Date columns: "Date", "date", "Transaction Date", "trans_date"
- Merchant columns: "Merchant_Name", "merchant", "Merchant", "Description"
- Category columns: "Category", "category", "Type"
- Amount columns: "Amount", "amount", "Value", "Debit"

### Option 2: Database to Vector DB Conversion Script
For enterprise users with existing databases (MySQL, PostgreSQL, MongoDB, etc.), we provide a **migration script** that:
- Connects to their existing database
- Extracts transaction data
- Converts it to vector embeddings
- Stores everything in Milvus

This is ideal for organizations wanting to migrate their legacy transaction systems to our AI-powered search without manual data entry.

---

## Security & Privacy - Plus Points

### ✅ No Data Leakage - Deploy On-Premise
- **Milvus is open-source** - Organizations can deploy it on their own servers
- Complete control over where data resides
- No third-party cloud services required
- Data never leaves your infrastructure

### ✅ Multiple Deployment Options

| Deployment | Data Location | Use Case |
|-----------|--------------|----------|
| Local/Machine | Your computer | Testing, personal use |
| On-Premise Server | Your data center | Enterprise, maximum security |
| Zilliz Cloud | Managed cloud | Scalability, ease of use |

### ✅ Data Isolation
- Each user gets a unique **API Key** stored in localStorage
- Multi-tenant architecture with data isolation
- Each user's data is stored separately with their unique API key

### ✅ Local Deployment Option
- Can run entirely locally using **Milvus Lite** (file-based)
- No data leaves the user's machine
- Ideal for privacy-conscious users or enterprise deployments

### ✅ Authentication
- API key-based authentication for all endpoints
- Keys are validated on every API request

### ✅ Data Encryption
- Milvus supports encryption at rest
- Zilliz Cloud (managed option) provides enterprise-grade security with encryption in transit and at rest

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | HTML/CSS/JavaScript (Chart.js for visualizations) |
| Backend | FastAPI (Python) |
| Vector DB | Milvus (Open Source) |
| Embedding Model | all-MiniLM-L6-v2 (Sentence Transformers) |
| Deployment | Docker, Local Server, Cloud, On-Premise |

---

## Key Features

1. **Natural Language Search** - Ask questions in plain English
2. **Smart Categorization** - Automatic transaction categorization
3. **Date-based Filtering** - "last month", "last week", "this year"
4. **Visual Dashboard** - Charts showing spending by category and merchant
5. **Multi-format Support** - CSV, Excel, JSON file uploads
6. **Database Migration** - Script to convert existing DB to vector DB
7. **Scalable** - Can handle millions of transactions
8. **Open Source** - Deploy anywhere, full control

---

## Current Status

- ✅ Core search functionality working
- ✅ Dashboard with charts
- ✅ Category detection
- ✅ Date range parsing
- ✅ API endpoints ready
- ✅ Multiple file format support
- ✅ Database to vector DB migration script available
- 🛠️ Upload/ingest functionality ready for integration

---

## Future Roadmap

1. **On-Premise Deployment Package** - Docker Compose for easy self-hosting
2. **Zilliz Cloud Integration** - Managed cloud deployment for easier scaling
3. **User Authentication** - Full login/signup system
4. **Data Visualization** - Enhanced charts and reports
5. **Multi-bank Integration** - Direct bank API connections (Plaid)
6. **Mobile App** - iOS/Android applications

---

## Investment Ask

We're seeking seed funding to:

- Build out the production-ready infrastructure
- Implement full user authentication system
- Add bank API integrations
- Develop mobile applications
- Marketing and user acquisition

---

## Why Invest in SAI?

1. **Growing Market** - Personal finance management is a $1.2B+ market
2. **AI-Powered** - Leverages latest in vector search and NLP
3. **Open Source Advantage** - No vendor lock-in, enterprise trust
4. **Privacy-First** - Deploy on-premise, no data leakage concerns
5. **Flexible Deployment** - Local, cloud, or on-premise

---

I'd love to schedule a demo to show you the system in action and discuss the investment opportunity further.

Looking forward to hearing from you.

Best regards,

Yokesh
[Your Title]
[Contact Information]

---

**Demo Link:** http://localhost:8001
**GitHub:** [Your GitHub Repository]
