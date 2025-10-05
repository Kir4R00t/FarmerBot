# Docs
## Bot commands
### # poe2scout 
To retrieve data about current currency market prices I use 
[poe2scout.com's website free API](https://poe2scout.com/api/swagger#/) <br>

When it comes to making good looking embeds to nicely display all desired currency prices all I had to do was create empty discord servers just to add emojis (it's a workaround for emoji limit of 50 for free servers) because the bot can use all emojis that it has access to on any server it's on.

### # gibcat
It's just a simple call to a [free cat pic API](https://thecatapi.com)

## Util scripts
### # get_currency_icons.py
Script that automatically downloads icons of all currencies from a given category (provided by a valid url to poe2scout.com API). <br>
File names of icons are set as 'apiId' of each currency so that it's then easier to match them later in the item_emojis file. <br>
To run the script you have to: <br> 
```python get_currency_icons.py <path_to_folder> <poe2scout_api_url>```