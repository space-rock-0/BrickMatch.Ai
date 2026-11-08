"""Legacy Streamlit interface retained for reference only.

The product UI is the vanilla single-page app in ``frontend/web/`` served by FastAPI at
``/``. This file is not started by the application or CI. Install the optional
``legacy`` extra if you need to inspect it.
"""
import os

import httpx
import streamlit as st

st.set_page_config(page_title="BrickMatch AI", page_icon="🧱", layout="wide")
st.markdown("""<style>
.stApp{background:#fff;color:#000;font-family:Arial,system-ui,sans-serif}
.block-container{max-width:1600px;padding:30px}
.brand{background:#ffd500;padding:24px 30px;margin-bottom:32px}
.stButton>button{border-radius:25px;font-size:18px;padding:12px 30px}
.stButton>button[kind="primary"]{background:#0058e6;color:#fff}
.stButton>button[kind="primary"]:hover{background:#0041b8}
a{color:#005ad2} input{border-color:#bfbfbf!important}
@media(max-width:700px){.block-container{padding:20px}}
</style><div class="brand"><h1>🧱 BrickMatch AI</h1><p>Build your next favorite.</p></div>""", unsafe_allow_html=True)
BASE = os.getenv("BRICKMATCH_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")


def request(path, payload=None):
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(BASE + path, json=payload) if payload is not None else client.get(BASE + path)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"Local API request failed: {exc}")
        return None


user = st.sidebar.text_input("Local profile", "builder", max_chars=80)
if not user or not all(char.isascii() and (char.isalnum() or char in "_-") for char in user):
    st.warning("Use letters, digits, underscores or hyphens for your profile.")
    st.stop()
st.sidebar.caption("Local profile selection is not secure authentication.")
page = st.sidebar.radio("Explore", ["Discover", "Swipe", "For You", "My Preferences", "Model Lab", "System Info"])


def card(item, key, explanations=None):
    with st.container(border=True):
        if item.get("image_available"):
            st.image(f"{BASE}/images/{item['set_id']}")
        else:
            st.markdown("### 🧱")
        st.subheader(item["name"])
        st.caption(f"{item['set_id']} · {item.get('theme', item['theme_id'])} · {item['year']} · {item['num_parts']:,} pieces")
        if not item.get("image_available"):
            st.caption("Image preview unavailable")
        for explanation in explanations or []:
            st.write(explanation)
        buttons = st.columns(3)
        for column, label, action in zip(buttons, ["♡ Like", "Dislike", "Skip"], ["like", "dislike", "skip"]):
            if column.button(label, key=f"{key}-{item['set_id']}-{action}") and request("/feedback", {"user_id": user, "set_id": item["set_id"], "action": action}):
                    st.rerun()


if page in {"Discover", "Swipe"}:
    st.markdown('<h2 style="text-align:center">Your next build starts here.</h2>', unsafe_allow_html=True)
    query = st.text_input("Search sets")
    cols = st.columns(3)
    theme = cols[0].number_input("Theme ID (0 for all)", min_value=0, value=0)
    year = cols[1].number_input("Released since", min_value=1949, max_value=2200, value=1949)
    parts = cols[2].number_input("Maximum pieces", min_value=0, max_value=100000, value=100000)
    offset = st.number_input("Page", min_value=1, value=1) - 1
    params = httpx.QueryParams({"q": query, "min_year": year, "max_parts": parts, "offset": offset * 12, "limit": 12})
    if theme:
        params = params.set("theme", theme)
    with st.spinner("Loading catalog…"):
        data = request(f"/sets?{params}")
    if data:
        st.caption(f"{data['total']} matching sets. Source age ratings are unavailable.")
        if not data["items"]:
            st.info("No sets found. Change filters or ingest a catalog and restart the API.")
        if page == "Swipe":
            feedback = request(f"/users/{user}/feedback")
            rated = {row["set_id"] for row in feedback["current"]} if feedback else set()
            remaining = [item for item in data["items"] if item["set_id"] not in rated]
            if remaining:
                card(remaining[0], "swipe")
            else:
                st.info("No unrated sets on this page. Open another page to continue.")
        else:
            columns = st.columns(3)
            for index, item in enumerate(data["items"]):
                with columns[index % 3]:
                    card(item, "discover")
elif page == "For You":
    st.title("Made for your next build")
    with st.spinner("Finding recommendations…"):
        data = request(f"/users/{user}/recommendations?k=12")
    if data:
        st.caption(f"{data['mode']} · {data['model_version']} · {data['generated_at']}")
        if not data["items"]:
            st.info("No eligible sets remain. Add catalog data or undo a rating.")
        columns = st.columns(3)
        for index, item in enumerate(data["items"]):
            with columns[index % 3]:
                card(item["set"], "recommendation", item["explanations"])
elif page == "My Preferences":
    st.title("Your building taste")
    data = request(f"/users/{user}/feedback")
    if data and data["current"]:
        st.dataframe(data["current"], use_container_width=True)
        chosen = st.selectbox("Undo rating for set", [row["set_id"] for row in data["current"]])
        if st.button("Undo rating") and request("/feedback", {"user_id": user, "set_id": chosen, "action": "undo"}):
                st.rerun()
    else:
        st.info("Your preferences appear here after your first rating.")
elif page == "Model Lab":
    st.title("Model Lab")
    info = request("/models/current")
    if info:
        st.json(info)
    metrics = request("/metrics")
    if metrics:
        st.caption(f"Recommendation requests: {metrics.get('recommendation_requests')} - last latency: {metrics.get('last_recommendation_ms')} ms")
else:
    st.title("System Info")
    for endpoint in ["/models/current", "/metrics"]:
        data = request(endpoint)
        if data:
            st.json(data)
st.divider()
st.caption("Independent portfolio project. Not affiliated with or endorsed by the LEGO Group.")
