FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY session_baton/ session_baton/
RUN pip install --no-cache-dir .
EXPOSE 9101
CMD ["python", "-m", "session_baton"]
