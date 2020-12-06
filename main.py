import html
import json
import os
import time
from datetime import datetime
from urllib.parse import unquote

import requests

DEFAULT_CONFIG = {
    "feeds": {}
}
CONFIG_FILE_NAME = "config.json"
HISTORY_FILE_NAME = "history.json"


def load_config():
    print("Loading config...")
    with open(CONFIG_FILE_NAME, "r") as f:
        data = json.loads(f.read())
    return data


def load_history(config):
    print("Loading history...")
    res = {key: None for key in config['feeds'].keys()}
    if os.path.isfile(HISTORY_FILE_NAME):
        with open(HISTORY_FILE_NAME, "r") as f:
            data = json.loads(f.read())
            for key, value in data.items():
                res[key] = value
    return res


def save_history(history):
    print("Saving history...")
    with open(HISTORY_FILE_NAME, "w") as f:
        f.write(json.dumps(history, indent=2))


def check_config(config):
    print("Checking config...")
    for feed, feed_config in config['feeds'].items():
        if feed_config['url'] == "" or feed_config['url'] is None:
            return False, f"Feed {feed} has invalid url."
        if feed_config['webhook'] == "" or feed_config['webhook'] is None:
            return False, f"Feed {feed} has invalid webhook url."
        if feed_config['nsfw'] not in ["on", "off", "only"]:
            return False, f"Feed {feed} has invalid nsfw value. Must be one of ['show', 'hide', 'only']."
        if type(feed_config['min_score']) != int:
            return False, f"Feed {feed} min_score is not a number."
        if type(feed_config['min_age_secs']) != int:
            return False, f"Feed {feed} min_age_secs is not a number."
        if type(feed_config['min_age_secs']) < 0:
            return False, f"Feed {feed} min_age_secs must be a positive number."
    return True, ""

def urldecode(text):
    return html.unescape(unquote(text))


if __name__ == '__main__':
    config = load_config()
    res, reason = check_config(config)

    history = load_history(config)

    for feed, feed_config in config['feeds'].items():
        print(f"Checking feed {feed}...")
        res = requests.get(feed_config['url'], headers={'User-Agent': "Linux:FeedBot:0.1 (by /u/Kanakonn)"})
        post_data = res.json()
        try:
            posts = post_data['data']['children']
        except KeyError:
            if post_data['error']:
                print(f"Error during processing of {feed}: {post_data['error']}, {post_data['reason']}. Message: {post_data['message']}")
            continue

        # Find previous position
        if history[feed] is not None:
            post_ids = [post['data']['id'] for post in posts]
            try:
                previous_position = post_ids.index(history[feed])
            except ValueError:
                previous_position = min(len(posts), 10)
        else:
            previous_position = min(len(posts), 10)

        # Filter posts and reverse list so oldest posts get posted first.
        posts = list(reversed(posts[:previous_position]))

        # If there are more than 10 entries, filter them out to 10 so we don't post too much in one go
        # The missed posts will be posted in the next iteration.
        if len(posts) > 10:
            posts = posts[:10]

        if len(posts) > 0:
            print(f"{len(posts)} new posts since post {history[feed]}.")
            for post in posts:
                post = post['data']
                print(f"Processing post {post['id']}")

                # Check age of post before doing anything else (we want to process it again later)
                if datetime.now().timestamp() - post['created_utc'] < feed_config['min_age_secs']:
                    print(f"Skipping post due to minimum age not reached "
                          f"(age {datetime.now().timestamp() - post['created_utc']}, "
                          f"min age {feed_config['min_age_secs']})")
                    continue

                # Add post to history so it won't be processed again
                history[feed] = post['id']

                # If post is not an image, skip it
                if 'post_hint' in post and post['post_hint'] != "image":
                    print(f"Skipping post due to no image: '{post['post_hint']}'")
                    continue

                # If post has no type hint (probably not an image), skip it
                if 'post_hint' not in post:
                    print(f"Skipping post due to no valid post_hint.")
                    continue

                # If post has too low score, skip it
                if post['score'] < feed_config['min_score']:
                    print(f"Skipping post due to low score: {post['score']} < {feed_config['min_score']}")
                    continue

                # If post is NSFW but we want no nsfw, skip it
                if feed_config['nsfw'] == "hide" and post['over_18']:
                    print("Skipping post due to NSFW")
                    continue

                # If post is not NSFW but we want only nsfw, skip it
                if feed_config['nsfw'] == "only" and not post['over_18']:
                    print("Skipping post due to not NSFW")
                    continue

                res = requests.post(url=feed_config['webhook'], json={
                    'username': f"/{post['subreddit_name_prefixed']}",
                    'embeds': [
                        {
                            'title': f"{urldecode(post['title'])} - {post['score']} points",
                            'url': f"https://old.reddit.com{post['permalink']}",
                            'image': {
                                'url': f"{post['url']}"
                            },
                            'author': {
                                'name': f"{post['subreddit_name_prefixed']}",
                                'url': f"https://old.reddit.com/{post['subreddit_name_prefixed']}"
                            },
                            'footer': {
                                'text': f"/u/{post['author']}"
                            }
                        }
                    ]
                })
                print(f"Result: {res.status_code}")
                time.sleep(1)
        else:
            print(f"No new posts found since post {history[feed]}.")
            time.sleep(1)

    save_history(history)
