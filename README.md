# FarmerBot
Discord bot made 100% in python for [official xfarmerx's discord](https://discord.com/invite/bsjQV4tFMf)

## Available commands & other features
```/poe2scout <currency_type> <reference_currency>``` - Queries poe2scout.com website for recent currency prices with ability to choose which currency you want to refer prices to<br>
```/gibcat``` - Gets an image of a sweet kitty <br>

```#Pricecheck request validator``` - If anyone asks for a pricecheck on their item and will not provide a valid link to poe2trade site to item with similar attributes the message will be deleted and it's gonna be followed up by bot's message .

## Upcoming features
- Adding rest of currency categories, so far I have basic currency, soul cores & essences
- Showing difference in currency prices from last market fetch

## Contributing
If you wish to contribute to the project please follow these general steps:
1. Fork the repository on github.
2. Clone your forked repository to your local machine. `git clone <forked_repo_url>`
3. Create a new branch `git checkout -b feature/your-feature-name`
4. Make your changes.
5. Commit your changes `git commit -m 'Added feature X'`
6. Push to the branch `git push origin feature/your-feature-name`.
7. Open a pull request

## Setting up local development enviorment
#### Windows
```python -m venv .venv```<br>
```pip install -r requirements.txt```<br>
```.\.venv\Scripts\Activate.ps1```

#### Linux
```python3 -m venv .venv```<br>
```source .venv/bin/activate```<br>
```pip install -r requirements.txt```<br>

## Docker deployment
```docker compose up --build```

## License
This project is licensed under the MIT license
