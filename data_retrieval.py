#!/usr/bin/env python
# coding: utf-8

# In[21]:


import praw
import requests
import datetime
import json
import asyncio
import nest_asyncio
from pyppeteer import launch
import re

CLIENT_ID = 'HIDDEN'
CLIENT_SECRET = 'HIDDEN'
USER_AGENT = 'HIDDEN'

# Initialize PRAW with your Reddit app credentials
reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    user_agent=USER_AGENT
)

def get_all_posts_from_subreddit_within_max_age(subreddit_name, data, max_age_days = 30):
# Define the subreddit and timeframe
    subreddit = reddit.subreddit(subreddit_name)
    
    # Calculate the timestamp for one month ago
    age_limit = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
    age_limit_timestamp = int(age_limit.timestamp())
    
    # Retrieve and filter posts from the subreddit
    i = 0
    num_errors = 0
    for submission in subreddit.new(limit=None):  # Fetches posts from the newest
        i+=1
        if i % 10 == 0:
            print(i)
        if submission.created_utc >= age_limit_timestamp:
            try:
                comments_with_text = []
                for comment in submission.comments:
                    if hasattr(comment, 'body'):
                        comments_with_text.append(comment)
    
                if comments_with_text:
                    sorted_comments_with_text = sorted(comments_with_text, key=lambda comment: comment.score, reverse=True)
                    data[submission.title] = [comment.body for comment in sorted_comments_with_text]
            except:
                num_errors += 1
                print('retrieval error')
        else:
            # Since posts are fetched in reverse chronological order, break when an older post is found
            break
        
    # Output the results
    print("Num post retrieval errors:", num_errors)
    return posts


# In[22]:


def get_reddit_posts(max_age_days = 30):
    for subreddit in ['fantasyfootball', 'fantasyfootballadvice', 'Fantasy_Football']:
        data = {}
        print(f"Getting posts from subreddit {subreddit}")
        get_all_posts_from_subreddit_within_max_age(subreddit, data, max_age_days)
        print("Dumping info so far.")
        old_data = {}
        combined_data = {}
        with open('reddit_posts.json', 'r') as file:
            old_data = json.load(file)
            combined_data = {**old_data, **data}
        with open('reddit_posts.json', 'w') as file:
            json.dump(combined_data, file)
            print(f"Num Reddit Posts Added: {len(combined_data) - len(old_data)}")
            print(f"Num Reddit Posts Stored: {len(combined_data)}")
    print("Posts found:", len(data))


# In[23]:


# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

async def extract_all_player_news(url='https://fantasy.espn.com/football/playernews', days=30):
    browser = await launch(headless=True)

    page = await browser.newPage()

    # Set a User-Agent header
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    await page.goto(url, {'waitUntil': 'networkidle2'})

    # Wait for the player-news section to load
    while True:
        try:
            # Wait for the player-news section to be visible
            await page.waitForSelector('div.player-news', timeout=10000)
            break
        except asyncio.TimeoutError:
            pass

    # Initialize the list to collect all news
    all_news = []

    # Calculate the date threshold
    date_threshold = datetime.datetime.now() - datetime.timedelta(days=days)

    has_more = True

    while has_more:
        # Extract text from the entire player-news section
        content = await page.querySelectorEval('div.player-news', 'element => element.innerText')

        # Split the content into news items (assuming each item is separated by newline or some delimiter)
        news_items = content.split('\n')  # Adjust splitting logic as necessary

        # Current year for comparison
        current_year = datetime.datetime.now().year
        latest_news_date = ""
        all_news = []
        # Check each news item for date and update latest_news_date if necessary
        for item in news_items:
            # Extract the date using regex
            match = re.search(r'\b[A-Z]{3},\s[A-Z]{3}\s\d{2},\s\d{2}:\d{2}\s[APM]{2}\b', item)
            if match:
                date_str = match.group()
                try:
                    # Extract month and day from date_str
                    month_day_str = re.search(r'[A-Z]{3}\s\d{2}', date_str).group()
                    month_day = datetime.datetime.strptime(month_day_str, '%b %d')
                    
                    # Construct the full date with the inferred year
                    news_date = datetime.datetime.strptime(date_str + ' ' + str(current_year), '%a, %b %d, %I:%M %p %Y')
                    latest_news_date = news_date
                    # Adjust year if news_date is in the future
                    if news_date > datetime.datetime.now():
                        news_date = news_date.replace(year=current_year - 1)
                    
                    # Compare with date threshold
                    if news_date < date_threshold:
                        await browser.close()
                        return all_news
                    
                    all_news.append(item)
                except ValueError:
                    pass
            else:
                all_news.append(item)  # If no date is found, append the item anyway

        # Check if we need to continue fetching more items
        if has_more:
            # Check if there is a "Show More" button with class 'show-more' and click it
            show_more_button = await page.querySelector('button.show-more')

            if show_more_button:
                await show_more_button.click()
                await page.waitFor(2000)  # Wait for new content to load
            else:
                has_more = False
        print("Earliest Searched Date so far:", latest_news_date)

    await browser.close()

    return all_news


# In[30]:


async def get_player_news(days=30):
    # Run the function and print the results
    player_news = await extract_all_player_news(days=days)
    # Replace all empty string entries with "-&&-"
    replaced_list = [item if item != '' else '-&&-' for item in player_news]
    # Join all strings in the list together
    combined_string = ' '.join(replaced_list).strip()
    # Split the combined string by "-&&- -&&-"
    player_news = combined_string.split('-&&- -&&-')
    print(f"Retrieved {len(player_news)} news articles.")
    # add to player_news_json
    all_p_news = []
    i = 0
    with open('player_news.json', 'r') as file:
        all_p_news_file = json.load(file)
        all_p_news = all_p_news_file['player_news']
        old_p_news_set = set(all_p_news)
        for article in player_news:
            if article not in old_p_news_set:
                i+=1
                all_p_news.append(article)
    with open('player_news.json', 'w') as file:
        json.dump({"player_news": all_p_news}, file)
    print(f"Num Player News Added: {i}")
    print(f"Total Num Player News Stored: {len(all_p_news)}")



