# Line-Bot-Connect

This repository contains a LINE Bot application powered by Flask and Azure OpenAI.

## Environment Variables
Ensure the following variables are set before running the application:

- `LINE_CHANNEL_ACCESS_TOKEN` – access token for your LINE bot
- `LINE_CHANNEL_SECRET` – secret used to verify webhook signatures
- `AZURE_OPENAI_API_KEY` – API key for Azure OpenAI
- `AZURE_OPENAI_ENDPOINT` – Azure endpoint URL
- `AZURE_OPENAI_DEPLOYMENT_NAME` – model deployment name
- `SESSION_SECRET` – Flask session secret
- `LOG_LEVEL` – optional logging level (default: INFO)

You can copy `.env.example` to `.env` and update these values.

## Running Locally
Install dependencies and start the app:

```bash
pip install -e .
python app.py
```

Alternatively build the Docker image:

```bash
docker build -t line-bot-connect .
docker run -p 5000:5000 --env-file .env line-bot-connect
```
