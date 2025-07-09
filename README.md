# 📺 YouTube Transcript MCP Server

This is a FastAPI-based Model Context Protocol (MCP) server that fetches transcripts from a given YouTube channel and returns structured JSON responses, optionally with PDF generation support.

---

## 🚀 Features

- 🔍 Extracts channel ID from multiple YouTube URL formats (`/channel/`, `/@handle`, `/user/`, `/c/`)
- 🎥 Fetches latest videos via YouTube Data API or fallback scraping
- 📝 Retrieves transcripts using `youtube-transcript-api`
- 💬 Supports retry logic with exponential backoff for rate limits
- 🧾 Optionally generates downloadable PDF transcripts (via `/download_pdf`)
- ⚙️ Ready for Claude Desktop as an external tool
- 🌐 Deployable on Render.com or any containerized environment

---

## 🛠️ Installation

```bash
git clone https://github.com/your-username/youtube-transcript-mcp.git
cd youtube-transcript-mcp
pip install -r requirements.txt
