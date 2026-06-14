"""
shared/secrets.py
=================
Centralised API-key resolution for OpenAI.
Both the Report Generator and Scout Assistant need this.
"""
from __future__ import annotations

import os

import streamlit as st


def get_openai_api_key() -> str | None:
    """
    Return the OpenAI API key from, in order of precedence:
    1. Streamlit secrets (secrets.toml)
    2. OPENAI_API_KEY environment variable
    Returns None if neither is set, without raising.
    """
    try:
        key = st.secrets.get("OPENAI_API_KEY")
        if key:
            return str(key)
    except Exception:
        pass

    return os.getenv("OPENAI_API_KEY")
