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
    api_key = api_key or os.getenv("OPENAI_API_KEY")
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

    system_prompt = """
    You are a data analyst AI assistant. You will be provided with a chart or plot image and a user prompt.
    Analyze the image and respond to the user's question based on the data shown in the image. Give concise, accurate answers.
    Don't answer questions that are completly unrelated to the image.
    """
    
    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": system_prompt}]  
        },
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "image", "image_url": data_url}
            ]
        }
    ]

    # call chat completions (or whichever chat endpoint your client version exposes)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    # extract text robustly
    choice = resp.choices[0]
    msg = choice.message
    content = msg.get("content")
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # find first text part
        for part in content:
            if part.get("type") in (None, "output_text", "text"):
                return part.get("text") or part.get("content") or ""
    # fallback
    return resp
