# FarmerBot
Discord bot and data engineering project made in Python for
[official xfarmerx's discord](https://discord.com/invite/bsjQV4tFMf).

The project ingests Path of Exile 2 market data, stores historical snapshots in
PostgreSQL, exposes analytics through Discord slash commands, and includes a
foundation for Airflow-based orchestration.

## Available Commands & Features
```/poe2scout <currency_type> <reference_currency>``` - Queries poe2scout.com for recent currency prices.<br>
```/etlstatus``` - Shows recent ETL runs from PostgreSQL.<br>
```/topmovers <category> <reference_currency> <hours>``` - Shows biggest market price movements from stored snapshots.<br>
```/pricehistory <item_api_id> <category> <reference_currency> <days>``` - Shows historical prices for a selected item.<br>
```/gibcat``` - Gets an image of a sweet kitty.<br>

```#Pricecheck request validator``` - If anyone asks for a pricecheck on their item and will not provide a valid link to poe2trade site to item with similar attributes, the message will be deleted and followed up by bot's message.

## Data Engineering Features
- Python ETL pipeline for poe2scout API ingestion
- PostgreSQL raw, dimension, fact and mart layers
- Historical price snapshots and normalized poe2scout price logs
- Data quality issue tracking
- ETL run monitoring
- Docker Compose stack with PostgreSQL
- Airflow DAG entry point in `orchestration/airflow/dags`

## Upcoming Features
- Airflow deployment profile
- Kafka/event-driven alerts for price thresholds
- Creating links with queries for a given item to make price checking easier

## Setting Up Local Development Environment
#### Windows
```python -m venv .venv```<br>
```.\.venv\Scripts\Activate.ps1```<br>
```pip install -r requirements.txt```<br>
```pip install -r requirements-dev.txt```<br>

#### Linux
```python3 -m venv .venv```<br>
```source .venv/bin/activate```<br>
```pip install -r requirements.txt```<br>
```pip install -r requirements-dev.txt```<br>

## Docker Deployment
Create your local environment file:

```bash
cp .env.example .env
```

Set a strong `POSTGRES_PASSWORD` in `.env`.

```docker compose up --build```

PostgreSQL is not exposed on a host port. It is reachable only by services in
the Docker Compose network.

## VPS Deployment Notes
On a VPS, keep `postgres` without a `ports` section. To inspect the database,
SSH into the server and open `psql` inside the container:

```bash
ssh user@your-vps
cd /path/to/FarmerBot
docker compose exec postgres psql -U farmerbot -d farmerbot
```

If you changed `POSTGRES_USER` or `POSTGRES_DB`, use those values instead.

Do not open port `5432` in your firewall.

## Running Market Ingestion
Start PostgreSQL and the bot stack:

```docker compose up --build```

Run a one-off ETL job:

```docker compose --profile jobs run --rm market-ingestion```

Or run it locally:

```python -m bot.data.pipeline --category currency --reference-currency exalted --reference-currency chaos```

See `docs/architecture.md` for the data architecture.

## Contributing
If you wish to contribute to the project please follow these general steps:
1. Fork the repository on GitHub.
2. Clone your forked repository to your local machine. `git clone <forked_repo_url>`
3. Create a new branch `git checkout -b feature/your-feature-name`
4. Make your changes.
5. Commit your changes `git commit -m 'Added feature X'`
6. Push to the branch `git push origin feature/your-feature-name`.
7. Open a pull request.

## License
This project is licensed under the MIT license.
