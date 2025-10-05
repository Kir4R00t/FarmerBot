# FarmerBot
Discord bot made 100% in python for [official xfarmerx's discord](https://discord.com/invite/bsjQV4tFMf)

## Available commands
```/poe2scout <currency_type> <reference_currency>``` - Queries poe2scout.com website for recent currency prices with ability to choose which currency you want to refer prices to<br>
```/gibcat``` - Gets an image of a sweet kitty <br>

## Upcoming features
- Adding rest of currency categories, so far I have basic currency, soul cores & essences

## Setting up virtualenv
#### Windows
```python -m venv .venv```  <br>
```.\.venv\Scripts\Activate.ps1```

#### Linux
```python3 -m venv .venv```   <br>
```source .venv/bin/activate```

## Docker deployment
```docker compose up -d --build```