<h1 align="center">
  <br>
  <img src="images/logo.png" alt="Logo" width="200">
  <br>
  Friend Codes
  <br>
</h1>

<h3 align="center">Self-hosted Discord bot to manage your community's friend codes.</h3>

<p align="center">
<a href="https://github.com/itzsmoki/Friend-Codes/releases"><img width="120px" alt="GitHub Release" src="https://img.shields.io/github/v/release/itzsmoki/Friend-Codes"></a>
<a href="https://ko-fi.com/itzsmoki"><img width="110px" alt="Static Badge" src="https://img.shields.io/badge/Donate-Ko--fi-e3d6c6"></a>
</p>

<!--
<div align="center">
  <a href="#what-it-does">What it Does</a> •
  <a href="#how-to-install">How to Install</a> •
  <a href="#support-this-project">Donations</a> 
</div>
-->


## What it Does

This Discord bot makes managing and storing friend codes effortless. Users can add or remove their friend codes and quickly look up all codes linked to a specific user.

## Linux Setup (Debian)

To run the project correctly, you need to install the following dependencies on a Linux system.

-   **Python 3.8+**: Ensure you have Python 3.8 or a newer version.
-   **pip**: Python's package manager.
- **Required Libraries**: The bot requires the following libraries to be installed:
  - `discord.py`
  - `psnawp-api`
  - `pytz`
  - `python-dotenv`
  - `aiosqlite`


### 1. Clone the repository
First, clone the repository to your local machine using Git. Open a terminal and run:
```bash
git clone https://github.com/itzsmoki/Friend-Codes
cd Friend-Codes
```

### 2. Install Python and pip
```bash
sudo apt update
sudo apt install python3 python3-pip
```

### 3. Create a virtual environment (optional, but recommended)
It is recommended to create a virtual environment to manage dependencies in isolation. You can do this with the following commands:
```bash
python3 -m venv venv
source venv/bin/activate
```
### 4. Install the dependencies
```bash
pip install -r requirements.txt
```

### 5. Edit the variables file
Finally, before running the bot, make sure to edit the provided .env file and add all your required variables.
Example `.env` file:
```env
BOT_TOKEN=your_bot_token_here
NPSSO_TOKEN=your_NPSSO_token_here
SERVER_ID=your_server_id_here
```

## Run
Once everything is set up, you can start your bot by running the following command:
```bash
python3 bot.py
```
Make sure you have completed all configuration steps, including setting up your .env file with the correct variables.

## Usage
### User Commands
- `/add` - Add your friend code.
-  `/remove` - Remove your previously added friend code.
-  `/search` - Look up the friend codes of other users.
-  `/ping` - Test the bot's latency.

### Administrator-Only Commands
- `/set-channel` - Set the channel where the friend codes will be stored.
- `/reload` - Reload all messages containing friend codes (this is also performed automatically once a day).


## Support This Project!

This is a small project I created to learn and improve my skills. Your donations will help me enhance it further by adding advanced features and integrated services. Any support, big or small, is greatly appreciated and will contribute to making this tool better with each update.

<a href='https://ko-fi.com/P5P617I01D' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi1.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
