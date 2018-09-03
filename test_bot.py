import os
import sys
import time
import re
from slackclient import SlackClient
import arxiv

import sumy
from sumy.parsers.html import HtmlParser
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words


# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
ARXIV_REGEX = r'(https?://[^\s]+)'

lang = 'english'
tknz = Tokenizer(lang)
stemmer = Stemmer(lang)
summarizer = Summarizer(stemmer)


def summarize(string, num_sentence=3):
    parser = PlaintextParser(string, tknz)
    parser.stop_word = get_stop_words(lang)
    summ_string = ''
    for sentence in summarizer(parser.document, num_sentence):
        summ_string += str(sentence) + ' '
    return summ_string


def parse_arxiv(command):
    command = command.strip('>')
    links = re.findall(ARXIV_REGEX, command)
    arxiv_ids = []
    for link in links:
        arxiv_id = link.split('/')[-1]
        arxiv_id = arxiv_id.split('.pdf')[0]
        arxiv_ids.append(arxiv_id)
    articles = []
    print(arxiv_ids)
    if len(arxiv_ids) > 0:
        articles = arxiv.query(id_list=arxiv_ids)
    return articles


def format_arxiv(article, do_summarize=True):
    msg = 'Title: %s\n' % article['title']
    msg += 'Authors: %s\n' % ', '.join(article['authors'])
    abstract = ' '.join(article['summary'].split('\n'))
    msg += '\nAbstract (summarized): ' + summarize(abstract) + '\n\n'
    msg += 'PDF: %s' % article['pdf_url']
    return msg


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                return message, event["channel"]
    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
    # This is where you start to implement more commands!
    articles = parse_arxiv(command)
    if len(articles) > 0:
        response = 'Here is what I found on arXiv: '
        for article in parse_arxiv(command):
            response += '\n\n'
            response += format_arxiv(article)
    else:
        response = "Don't seem to find an arXiv link..."

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response
    )


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
