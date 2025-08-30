import os
import base64
from io import BytesIO
from PIL import Image
import plotly.graph_objects as go
from openai import OpenAI

# Load the API key from .env
import dotenv
dotenv.load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

system_prompt = """
You are a data-analyst AI assistant specializing in visual analysis of charts and plots for Victoria, Australia. Inputs: a user question and an image of a chart/plot that shows one of these datasets: building permits (Victoria), the transport network (Victoria), housing data (Victoria), or criminality data (Victoria).

Behavior:
- Answer only questions that can be resolved from the image.
- Be concise and direct. Lead with a 1-2 sentence conclusion (answer), then provide up to 3 short supporting bullets referencing what you see in the image (e.g., “line at x=..., peak at month Y, category Z highest”).
- Use metric/Australian conventions where applicable.
- You can use external knowledge about Victoria, Australia if it helps answering the question.

Tone: direct, evidence-driven
"""

def fig_to_png_bytes(fig: go.Figure, scale: int = 2) -> bytes:
    # plotly.kaleido to PNG bytes
    return fig.to_image(format="png", scale=scale)

def image_bytes_to_dataurl(b: bytes, mime="image/png") -> str:
    b64 = base64.b64encode(b).decode("ascii")
    return f"data:{mime};base64,{b64}"

def analyze_with_openai_client(prompt: str, *,
                               plotly_fig=None,
                               image_path: str = None,
                               model: str = "gpt-4o-mini",
                               max_tokens: int = 5000,
                               temperature: float = 0.0):
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY or pass api_key=...")

    # prepare image bytes
    if sum(bool(x) for x in (plotly_fig, image_path)) != 1:
        raise ValueError("Provide exactly one of: plotly_fig, image_path")

    if plotly_fig is not None:
        img_bytes = fig_to_png_bytes(plotly_fig)
    else:
        with open(image_path, "rb") as f:
            img_bytes = f.read()

    data_url = image_bytes_to_dataurl(img_bytes)

    client = OpenAI(api_key=api_key)
    
    messages = [
        {"role": "system",
         "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user",
         "content": [
             {"type": "text", "text": prompt},
             {"type": "image_url", "image_url": {"url": data_url}}
         ]}
    ]

    # call chat completions (or whichever chat endpoint your client version exposes)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content