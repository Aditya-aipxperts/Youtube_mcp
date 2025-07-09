import os, re, time, random, datetime, requests
from urllib.parse import urlparse
from fastapi import FastAPI
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, VideoUnavailable
from dotenv import load_dotenv

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

app = FastAPI()


def extract_channel_id(channel_url):
    try:
        channel_url = channel_url.strip().rstrip('/')
        if not channel_url.startswith(("http://", "https://")):
            channel_url = "https://" + channel_url
        parsed = urlparse(channel_url)
        path = parsed.path

        if '/channel/' in path:
            return path.split('/channel/')[1]
        elif '/@' in path:
            handle = path.split('/@')[1]
            search_url = (
                f"https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&type=channel&maxResults=1&q={handle}&key={YOUTUBE_API_KEY}"
            )
            response = requests.get(search_url, timeout=10).json()
            if response.get("items"):
                return response["items"][0]["snippet"]["channelId"]
        else:
            html = requests.get(channel_url, timeout=10).text
            match = re.search(r'"channelId":"(UC[0-9A-Za-z_-]{22})"', html)
            if match:
                return match.group(1)

        raise ValueError("Could not extract channel ID from URL")

    except Exception as e:
        raise ValueError(f"extract_channel_id failed: {e}")


def get_video_ids(channel_id, max_results=2):
    try:
        url = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?key={YOUTUBE_API_KEY}&channelId={channel_id}"
            f"&part=snippet,id&order=date&maxResults={max_results}&type=video"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        videos = []
        for item in data.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                videos.append({
                    "videoId": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "publishedAt": item["snippet"]["publishedAt"]
                })
        return videos
    except Exception as e:
        print(f"[API fallback failed] {e}")
        return []


def get_transcript(video_id, retries=5):
    for i in range(retries):
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return "\n".join([entry["text"] for entry in transcript])
        except TranscriptsDisabled:
            return "[Transcripts are disabled]"
        except VideoUnavailable:
            return "[Video is unavailable]"
        except Exception as e:
            if "429" in str(e):
                wait = (2 ** i) + random.randint(1, 5)
                print(f"Rate limited. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return f"[Error: {e}]"
    return "[Failed after retries]"


@app.get("/fetch_transcripts")
async def fetch_transcripts(channel_url: str, max_results: int = 2):
    try:
        channel_id = extract_channel_id(channel_url)
        videos = get_video_ids(channel_id, max_results)
        result = []
        for v in videos:
            result.append({
                "videoId": v["videoId"],
                "title": v["title"],
                "publishedAt": v["publishedAt"],
                "transcript": get_transcript(v["videoId"])
            })
        return {"transcripts": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/")
async def root():
    return {"status": "YouTube MCP server is running!"}
import os, re, time, random, datetime, requests
from urllib.parse import urlparse
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, VideoUnavailable
from mcp.server.fastmcp import FastMCP

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Initialize FastMCP
mcp = FastMCP("YouTubeTranscripts", stateless_http=True)


def extract_channel_id(channel_url):
    channel_url = channel_url.strip().rstrip('/')
    if not channel_url.startswith(("http://", "https://")):
        channel_url = "https://" + channel_url
    parsed = urlparse(channel_url)
    path = parsed.path
    if '/channel/' in path:
        return path.split('/channel/')[1]
    elif '/@' in path:
        handle = path.split('/@')[1]
        search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&maxResults=1&q={handle}&key={YOUTUBE_API_KEY}"
        res = requests.get(search_url, timeout=10).json()
        return res["items"][0]["snippet"]["channelId"] if res.get("items") else None
    else:
        html = requests.get(channel_url, timeout=10).text
        match = re.search(r'"channelId":"(UC[0-9A-Za-z_-]{22})"', html)
        return match.group(1) if match else None


def get_video_ids(channel_id, max_results=2):
    url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet,id&order=date&maxResults={max_results}&type=video"
    res = requests.get(url, timeout=10).json()
    videos = []
    for item in res.get("items", []):
        if item["id"]["kind"] == "youtube#video":
            videos.append({
                "videoId": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "publishedAt": item["snippet"]["publishedAt"]
            })
    return videos


def get_transcript(video_id, retries=3):
    for i in range(retries):
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return "\n".join([x["text"] for x in transcript])
        except TranscriptsDisabled:
            return "[Transcripts are disabled]"
        except VideoUnavailable:
            return "[Video is unavailable]"
        except Exception as e:
            if "429" in str(e):
                time.sleep((2 ** i) + random.randint(1, 3))
            else:
                return f"[Error: {e}]"
    return "[Failed after retries]"


@mcp.tool()
def fetch_transcripts(channel_url: str, max_results: int = 2) -> str:
    """
    Fetch and return short transcripts of recent YouTube videos from a channel.
    """
    channel_id = extract_channel_id(channel_url)
    if not channel_id:
        return "Could not extract channel ID."
    videos = get_video_ids(channel_id, max_results)
    output = []
    for v in videos:
        short_transcript = get_transcript(v["videoId"])[:100] + "…"
        output.append(f"📺 {v['title']}:\n{short_transcript}")
    return "\n\n".join(output)


# Expose these for import
session_manager = mcp.session_manager
streamable_http_app = mcp.streamable_http_app
