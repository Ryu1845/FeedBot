import json
import os
import time
import arrow
from typing import Dict
import feedparser
import requests

DEFAULT_CONFIG: Dict[str, Dict[str, str]] = {
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
    return True, ""


if __name__ == '__main__':
    config = load_config()
    res, reason = check_config(config)
    history = load_history(config)

    time_fmt = 'DD MMM YYYY HH:mm:ss'
    for feed, feed_config in config['feeds'].items():
        print(f"Checking feed {feed}...")
        post_data = feedparser.parse(feed_config['url'])
        posts = post_data.entries

        # Find previous position
        if history[feed] is not None:
            post_ids = list()
            for post in posts:
                published = arrow.get(post.published, time_fmt)
                post_ids.append(published.timestamp)
            try:
                previous_position = post_ids.index(history[feed])
            except ValueError:
                previous_position = min(len(posts), 10)
        else:
            previous_position = min(len(posts), 10)

        # Filter posts and reverse list so oldest posts get posted first.
        posts = list(reversed(posts[:previous_position]))

        # If there are more than 10 entries,
        # filter them out to 10 so we don't post too much in one go
        # The missed posts will be posted in the next iteration.
        if len(posts) > 10:
            posts = posts[:10]

        if len(posts) > 0:
            print(f"{len(posts)} new posts since post {history[feed]}.")
            for post in posts:
                post = post
                print(f"Processing post {post.title}")

                # Add post to history so it won't be processed again
                history[feed] = arrow.get(post.published, time_fmt).timestamp

                res = requests.post(url=feed_config['webhook'], json={
                    'username': f"/{post_data.feed.title}",
                    'embeds': [
                        {
                            'title': post.title,
                            'url': post.link,
                            'author': {
                                'name': post_data.feed.title,
                                'url': post_data.feed.link
                            },
                            'footer': {
                                'text': post_data.feed.subtitle
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
