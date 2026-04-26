# Gemini API — Project Rules

This document defines the **only two approved ways** to use Google's Gemini API in this project.
Read the decision guide below, pick one approach, and follow it exactly. Do not mix approaches or deviate from the patterns shown.

---

## Fixed Values (apply to BOTH approaches — never change these)

| Setting | Value |
|---|---|
| Project ID | `analytics-agent-487705` |
| Location | `global` |
| Model | `gemini-2.5-flash` |
| Auth file | `auth.json` (always in the project root) |
| Auth type | Service account (never API key) |

---

## How to Choose an Approach

| Use **Approach A** (`google-genai` direct) when... | Use **Approach B** (LangChain) when... |
|---|---|
| You only need to call the Gemini API | You need LangChain features: chains, agents, memory, output parsers, RAG, etc. |
| You want the simplest, most reliable setup | The rest of the codebase already uses LangChain |
| No LangChain dependency exists in the project | You need to plug the LLM into a LangChain pipeline |

**When in doubt, prefer Approach A.** It has fewer moving parts and was the first to work in this project.

---

---

# Approach A — `google-genai` Direct (Recommended)

## Stack

| Component | Value |
|---|---|
| Package | `google-genai` |
| Client class | `genai.Client` |
| API version | `v1` (must be set via `HttpOptions`) |

## Imports

```python
import os
from pathlib import Path
from google import genai
from google.genai.types import HttpOptions
```

## Setup (copy exactly — order matters)

```python
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path(__file__).parent / "auth.json")
os.environ["GOOGLE_CLOUD_PROJECT"] = "analytics-agent-487705"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

client = genai.Client(http_options=HttpOptions(api_version="v1"))
```

## Making a Request

```python
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Your prompt here",
)
print(response.text)
```

## Complete Working Example

```python
import os
from pathlib import Path
from google import genai
from google.genai.types import HttpOptions

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path(__file__).parent / "auth.json")
os.environ["GOOGLE_CLOUD_PROJECT"] = "analytics-agent-487705"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

client = genai.Client(http_options=HttpOptions(api_version="v1"))

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain supply chain delays simply",
)
print(response.text)
```

## Dependencies

```bash
pip install google-genai
```

## Approach A — Do NOT

- **Do NOT omit `HttpOptions(api_version="v1")`** — the client will use the wrong API version
- **Do NOT omit any of the 4 `os.environ` lines** — all four are required
- **Do NOT use `GOOGLE_API_KEY`** — auth is via service account only
- **Do NOT use `gcloud auth application-default login`** — credentials come from `auth.json`
- **Do NOT use LangChain wrappers** in this approach
- **Do NOT use `google-cloud-aiplatform` / `vertexai` SDK** — use `google-genai` only

---

---

# Approach B — LangChain (`ChatGoogleGenerativeAI`)

## Stack

| Component | Value |
|---|---|
| Package | `langchain-google-genai` |
| Class | `ChatGoogleGenerativeAI` |
| Auth scope | `https://www.googleapis.com/auth/cloud-platform` |
| `vertexai` flag | `True` |

## Imports

```python
import os
from pathlib import Path
from google.oauth2 import service_account
from langchain_google_genai import ChatGoogleGenerativeAI
```

## Setup (copy exactly — order matters)

```python
# Step 1: load credentials WITH the required scope
credentials = service_account.Credentials.from_service_account_file(
    str(Path(__file__).parent / "auth.json"),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

# Step 2: set environment variables
os.environ["GOOGLE_CLOUD_PROJECT"] = "analytics-agent-487705"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# Step 3: create the LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    credentials=credentials,
    project="analytics-agent-487705",
    location="global",
    vertexai=True,
)
```

## Making a Request

```python
response = llm.invoke("Your prompt here")
print(response.content)  # note: .content not .text
```

## Complete Working Example

```python
import os
from pathlib import Path
from google.oauth2 import service_account
from langchain_google_genai import ChatGoogleGenerativeAI

credentials = service_account.Credentials.from_service_account_file(
    str(Path(__file__).parent / "auth.json"),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

os.environ["GOOGLE_CLOUD_PROJECT"] = "analytics-agent-487705"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    credentials=credentials,
    project="analytics-agent-487705",
    location="global",
    vertexai=True,
)

print(llm.invoke("Explain supply chain delays simply").content)
```

## Dependencies

```bash
pip install langchain-google-genai google-auth
```

## Approach B — Do NOT

- **Do NOT use `ChatVertexAI`** from `langchain-google-vertexai` — deprecated and broken for this project
- **Do NOT install or import `langchain-google-vertexai`** — only `langchain-google-genai` is approved
- **Do NOT omit `scopes=["https://www.googleapis.com/auth/cloud-platform"]`** when loading credentials — omitting it causes `invalid_scope` token refresh error
- **Do NOT pass only `GOOGLE_APPLICATION_CREDENTIALS`** as the auth method — credentials must be constructed explicitly with scopes and passed directly to the constructor
- **Do NOT omit `vertexai=True`** from the `ChatGoogleGenerativeAI` constructor
- **Do NOT use `GOOGLE_API_KEY`** — auth is via service account only
- **Do NOT call `response.text`** — LangChain returns an `AIMessage`; use `response.content`

---

---

## Shared Rules (apply to BOTH approaches)

- **Do NOT change the model** — always `gemini-2.5-flash`
- **Do NOT change the location** — always `global`, never `us-central1` or any other region
- **Do NOT change the project ID** — always `analytics-agent-487705`
- **Do NOT hardcode the path to `auth.json`** — always resolve it with `Path(__file__).parent / "auth.json"`
- **Do NOT use alternate model names** such as `gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-2.0-flash-001`, `gemini-1.5-flash-002` — they will 404
- **Do NOT load credentials from `.env`** — set them in code as shown above
