📊 Apex Institutional Sentiment Engine
An AI-powered financial news intelligence system that converts unstructured business news into structured events, signals, and company health insights.

Live Demo: https://apex-institutional-sentiment-engine.onrender.com

🚀 Overview
Apex ISE is a streaming AI pipeline that processes financial news articles and transforms them into structured, analyzable intelligence.
Instead of reading individual news articles, the system:
news → events → signals → dashboard insights
It is designed to simulate how institutional-grade sentiment systems might structure and analyze market-relevant information.

🧠 What it does
Scrapes company-specific financial news
Extracts structured events using a local LLM (Llama 3.1 8B / Gemini depending on setup)
Dynamically builds and updates an event taxonomy
Converts events into weighted signals with time-decay logic
Stores everything in SQLite for traceability
Visualizes results in an interactive dashboard

⚙️ Architecture
News Sources
    ↓
Scraper (Moneycontrol / tag pages)
    ↓
Article Fetcher
    ↓
LLM Event Extractor
    ↓
Event Registry (dynamic taxonomy)
    ↓
Signal Generator (time decay + scoring)
    ↓
SQLite Database
    ↓
Dashboard UI (analytics + sector view)

🧩 Key Features

🔹 Streaming Processing
Each article is processed one at a time to ensure memory efficiency and system stability.

🔹 LLM-Based Event Extraction
Extracts structured events such as:

Earnings reports
Layoffs
Contracts
Acquisitions
Regulatory updates

🔹 Dynamic Event Taxonomy
The system can introduce new event types when unseen patterns appear, while preventing duplicates through similarity matching.

🔹 Signal Engine
Events are converted into signals with:

Direction (positive / negative / neutral)
Confidence scoring
Time-decay weighting

🔹 SQLite Persistence
All events, signals, and registry updates are stored in a structured relational database.

🔹 Interactive Dashboard
A lightweight frontend that displays:

Event breakdowns
Sector/company health signals
Source traceability

🛠️ Tech Stack
Python 3.11
SQLite
LLMs (Llama 3.1 8B / Gemini API depending on setup)
BeautifulSoup / Requests (scraping)
Vanilla HTML, CSS, JavaScript (frontend)
Render (deployment)

▶️ How to Run Locally
1. Clone repo
git clone https://github.com/lucky-rar007/Apex_Institutional_Sentiment_Engine
cd Apex_Institutional_Sentiment_Engine
2. Install dependencies
pip install -r requirements.txt
3. Configure environment (if required)

Example:

GEMINI_API_KEY=your_key_here
4. Run the pipeline
python main.py

You will be prompted to select the dataset / source file.

5. Access dashboard
http://localhost:8000
API layer for external access
Authentication + multi-user dashboards
