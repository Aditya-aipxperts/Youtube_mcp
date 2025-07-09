import os, re, time, random, datetime, requests
from urllib.parse import urlparse
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, VideoUnavailable
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from fpdf import FPDF

# Initialize FastMCP
mcp = FastMCP("YouTubeTranscripts", stateless_http=True)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def extract_channel_id(channel_url):
    """Extract YouTube channel ID from URL: supports /channel/, /@handle, /user/, /c/."""
    try:
        # Clean URL
        channel_url = channel_url.strip().rstrip('/')
        if not channel_url.startswith(("http://", "https://")):
            channel_url = "https://" + channel_url

        parsed = urlparse(channel_url)
        path = parsed.path

        # Case 1: Direct channel ID
        if '/channel/' in path:
            return path.split('/channel/')[1]

        # Case 2: Handle - /@pewdiepie
        elif '/@' in path:
            handle = path.split('/@')[1]
            search_url = (
                f"https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&type=channel&maxResults=1&q={handle}&key={YOUTUBE_API_KEY}"
            )
            response = requests.get(search_url, timeout=10).json()
            if response.get("items"):
                return response["items"][0]["snippet"]["channelId"]

        # Case 3: Legacy URLs like /user/ or /c/
        else:
            # Fallback to scraping
            response = requests.get(channel_url, timeout=10)
            html = response.text
            match = re.search(r'"channelId":"(UC[0-9A-Za-z_-]{22})"', html)
            if match:
                return match.group(1)

        raise ValueError("Could not extract channel ID from URL")

    except Exception as e:
        raise ValueError(f"extract_channel_id failed: {e}")
    

def get_video_ids(channel_id, max_results=2):
    """Fetch latest video IDs from a channel using API (fallback: scraping)."""
    video_ids = []

    # ✅ METHOD 1: Use YouTube Data API
    try:
        url = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?key={YOUTUBE_API_KEY}&channelId={channel_id}"
            f"&part=snippet,id&order=date&maxResults={max_results}&type=video"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("items"):
            for item in data["items"]:
                if item["id"]["kind"] == "youtube#video":
                    video_ids.append({
                        "videoId": item["id"]["videoId"],
                        "title": item["snippet"]["title"],
                        "publishedAt": item["snippet"]["publishedAt"]
                    })

        if video_ids:
            return video_ids

    except Exception as e:
        print(f"[API Fallback] Failed to get videos via API: {e}")

    # ❌ METHOD 2: Fallback to scraping
    try:
        url = f"https://www.youtube.com/channel/{channel_id}/videos"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        html = response.text

        # Extract videoId from HTML
        matches = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        unique_ids = list(set(matches))[:max_results]

        for vid in unique_ids:
            video_ids.append({
                "videoId": vid,
                "title": f"Video {vid}",
                "publishedAt": datetime.now().isoformat()
            })

        return video_ids

    except Exception as e:
        print(f"[Scrape Fallback] Failed to scrape video IDs: {e}")
        return []

def get_transcript_with_backoff(video_id, max_retries=5):
    for i in range(max_retries):
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return "\n".join([entry["text"] for entry in transcript])
        except TranscriptsDisabled:
            return "[Transcripts are disabled for this video]"
        except VideoUnavailable:
            return "[Video is unavailable or private]"
        except Exception as e:
            if "429" in str(e):
                wait = (2 ** i) + random.randint(1, 5)
                print(f"⏳ Rate limited. Retrying in {wait} seconds...")
                time.sleep(wait)
            else:
                return f"[Error getting transcript: {e}]"
    return "[Failed after multiple retries]"


def save_transcripts_to_pdf(channel_id, transcripts):
    os.makedirs("outputs", exist_ok=True)
    filename = f"outputs/{channel_id}_transcripts.pdf"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ➤ Register a Unicode-capable TrueType font
    pdf.add_font('DejaVu', '', '/path/to/DejaVuSans.ttf', uni=True)
    pdf.set_font("DejaVu", size=10)

    for video in transcripts:
        pdf.add_page()
        pdf.set_font("DejaVu", 'B', 12)
        pdf.multi_cell(0, 10, video['title'])
        pdf.set_font("DejaVu", size=10)
        pdf.ln(5)
        pdf.multi_cell(0, 8, video['transcript'])
    pdf.output(filename)
    print(f"\n✅ Saved transcripts to PDF: {filename}")

@mcp.tool()
def fetch_transcripts(channel_url: str, max_results: int = 2) -> str:
    channel_id = extract_channel_id(channel_url)
    videos = get_video_ids(channel_id, max_results)
    transcripts = []
    for v in videos:
        transcripts.append(get_transcript_with_backoff(v["videoId"])[:60] + "…")
    return f"Fetched {len(transcripts)} transcripts: " + " | ".join(transcripts)

# Convert FastMCP to ASGI app
mcp_app = mcp.sse_app()

# Create FastAPI and mount MCP endpoint
app = FastAPI()
app.mount("/mcp", mcp_app)

@app.get("/fetch_transcripts")
async def fetch_transcripts_api(channel_url: str, max_results: int = 2):
    """
    FastAPI endpoint for fetching full YouTube transcripts.
    """
    channel_id = extract_channel_id(channel_url)
    videos = get_video_ids(channel_id, max_results)
    results = []
    for v in videos:
        transcript = get_transcript_with_backoff(v["videoId"])
        results.append({
            "videoId": v["videoId"],
            "title": v["title"],
            "publishedAt": v["publishedAt"],
            "transcript": transcript
        })
    return {"transcripts": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
