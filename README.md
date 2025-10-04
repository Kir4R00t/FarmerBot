# FarmerBot
Discord bot made 100% in python for official xfarmerx's discord

## Available commands
```/poe2scout <currency_type> ``` - Queries poe2scout.com website for recent currency prices<br>
```/gibcat``` - Gets an image of a sweet kitty <br>

## Upcoming features
- Refractor of all currency categories
- Adding a way to change base currency equivalent (from exalts to for example chaos)

## Setting up virtualenv
#### Windows
```python -m venv .venv```  <br>
```.\.venv\Scripts\Activate.ps1```

#### Linux
```python3 -m venv .venv```   <br>
```source .venv/bin/activate```

## Docker deployment
```docker compose up -d --build```