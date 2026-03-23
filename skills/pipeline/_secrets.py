"""
_secrets.py — 统一密钥管理
所有 pipeline 脚本必须从这里导入 GROQ_KEY，禁止硬编码
"""
import os

GROQ_KEY = os.environ.get(
    "GROQ_API_KEY",
    "***REDACTED***"
)
assert GROQ_KEY.startswith("gsk_"), "GROQ_API_KEY 未设置或格式错误！"
