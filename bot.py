import httplib2, os, time, oauth, datetime, sys, socket
from slackclient import SlackClient
from apiclient import discovery
from oauth2client import client, tools
from oauth2client.file import Storage
from slackclient import SlackClient
try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output

    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and ("<@" + BOT_ID + ">") in output['text']:
                # return text after the @ mention, whitespace removed
                text = output['text'].split(("<@" + BOT_ID + ">"))
                if text[0].strip().lower() in hello_words:
                    slack_client.api_call("chat.postMessage",
                        channel=output['channel'],
                        text=("Hello " + "<@" + output['user'] + ">!"),
                        as_user=True)
                if text[0].strip().lower().startswith("thank"):
                    slack_client.api_call("chat.postMessage",
                        channel=output['channel'],
                        text=("You're welcome " + "<@" + output['user'] + ">!"),
                        as_user=True)
                else:
                    return text[1].strip().lower(), output['channel'], output['user']
    return None, None, None

# Get the name for the person doing support on today day
def get_name_from_cal():
    """
        Search today's events, looking for "Atmosphere Support".

        Returns:
            Name string
    """
    # Check next 24 hours
    now = datetime.datetime.utcnow()
    later = now + datetime.timedelta(hours=23)
    now = now.isoformat() + 'Z' # 'Z' indicates UTC time
    later = later.isoformat() + 'Z'
    eventsResult = service.events().list(
        calendarId=CAL_ID, timeMin=now, timeMax=later, singleEvents=True,
        orderBy='startTime').execute()
    events = eventsResult.get('items', [])

    # Search through events looking for 'Atmosphere Support'
    if events:
        for event in events:
            desc = event['summary']
            # If the event matches, return the first word of summary which is name
            if "Atmosphere Support" in desc:
                return desc.split()[0]
    return "no one is on support today"

def get_day_from_cal(name):
    """
        Search upcoming events, looking for the specified name.

        Returns:
            Day string ("Monday", etc.)
    """
    # Check next week
    now = datetime.datetime.utcnow()
    now = now.isoformat() + 'Z' # 'Z' indicates UTC time
    eventsResult = service.events().list(
        calendarId=CAL_ID, timeMin=now, singleEvents=True,
        orderBy='startTime').execute()
    events = eventsResult.get('items', [])

    # Search through events
    if events:
        for event in events:
            desc = event['summary']
            if name.lower() in desc.lower() and "Atmosphere Support" in desc:
                date = datetime.datetime.strptime(event['start'].get('dateTime', event['start'].get('date')), "%Y-%m-%d")
                # Return day of week as full string
                return date.strftime("%A") + " " + date.strftime("%Y-%m-%d")
    return "not on the calendar"

def handle_command(command, channel, user):
    """
        Manages the commands 'who', 'when', 'why', 'where', and 'how'.
        Also responds to a list of hello_words
        No return, sends message to Slack.
    """
    command = command.lower().split()
    command_response_dict = {"who"    : "Today's support person is %s." % ("<@" + get_user_id(slack_client, get_name_from_cal()) + ">"),
                             "when"   : find_when(command, user),
                             "why"    : "because we love our users!",
                             "where"  : "This bot is hosted on %s in the directory %s.\nYou can find my code here: %s." % (socket.getfqdn(), os.getcwd(), "https://github.com/calvinmclean/cyverse-support-bot"),
                             "how"    : "%s or %s" % ("http://cerberus.iplantcollaborative.org/rt/", "https://app.intercom.io/a/apps/tpwq3d9w/respond")}
    if command[0] in hello_words:
        response = "Hello!"
    elif command[0] in command_response_dict:
        response = command_response_dict[command[0]]
    else:
        response = "Ask me:\n  `who` is today's support person.\n  `when` is someone's next day\n  `where` I am hosted\n  `how` you can support users\n  `why`"
    slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)

def find_when(name, user):
    """
        Finds ther user's next support day.

        Argument 'name' is a list. If the first word is not 'when', then ignore.
        If no username is specified after 'when', find it based off asking user's ID.
    """
    if name[0] != "when":
        return "Command is not 'when'"
    elif len(name) <= 1:
        response = "The next support day for %s is %s." % (("<@" + user + ">"), get_day_from_cal(get_user_name(slack_client, user)))
    else:
        # Check if name exists in user list
        if get_user_id(slack_client, name[1]):
            response = "The next support day for %s is %s." % (("<@" + get_user_id(slack_client, name[1]) + ">"), get_day_from_cal(name[1]))
        else:
            response = "User %s does not seem to exist in this team." % (name[1])
    return response

def get_credentials():
    """
        Gets valid user credentials from storage.

        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.

        Returns:
            Credentials, the obtained credential.
    """
    credential_path = GOOGLE_APP_OAUTH_SECRET_PATH
    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(GOOGLE_APP_SECRET_PATH,
		'https://www.googleapis.com/auth/calendar.readonly')
        flow.user_agent = 'Cyverse Slack Supurt But'
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + GOOGLE_APP_OAUTH_SECRET_PATH)
    return credentials

def get_user_id(slack_client, name):
    """
        Gets valid user id from username.

        Returns:
            User ID of bot.
    """
    for user in user_list:
        if 'name' in user and user.get('name') == name:
            return user.get('id')
    return None

def get_user_name(slack_client, id):
    """
        Gets valid username from user id.

        Returns:
            Username.
    """
    for user in user_list:
        if 'id' in user and user.get('id') == id:
            return user.get('name')
    return None

# constants
CAL_ID = os.environ.get("CAL_ID")
BOT_NAME = os.environ.get("BOT_NAME")
BOT_ID = None
GOOGLE_APP_SECRET_PATH = os.environ.get("GOOGLE_APP_SECRET_PATH")
GOOGLE_APP_OAUTH_SECRET_PATH = os.environ.get("GOOGLE_APP_OAUTH_SECRET_PATH", ".oauth_secret_json")
BOT_USER_OAUTH_TOKEN=os.environ.get('BOT_USER_OAUTH_TOKEN')
SUPPORT_CHANNEL=os.environ.get('SUPPORT_CHANNEL', 'general')
hello_words = {'hello', 'hi', 'howdy', 'hey', 'good morning'}
slack_client = SlackClient(BOT_USER_OAUTH_TOKEN)
user_list = None

if __name__ == "__main__":

    # OAUTH
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    # Get list of users so it API doesn't have to be asked for list each time
    api_call = slack_client.api_call("users.list")
    if api_call.get('ok'):
        user_list = api_call.get('members')

    # SLACK
    BOT_ID = get_user_id(slack_client, BOT_NAME)
    if slack_client.rtm_connect():
        while True:
            # wait to be mentioned
            command, channel, user = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel, user)

            cur_time = time.localtime()
            # or print today's support name if it is a weekday at 8am
            if cur_time.tm_wday < 5 and cur_time.tm_hour == 8 and cur_time.tm_min == 0 and cur_time.tm_sec == 0:
                handle_command("who", SUPPORT_CHANNEL, None)
                slack_client.api_call("chat.postMessage", channel=SUPPORT_CHANNEL, text="Don't forget Intercom! :slightly_smiling_face:", as_user=True)
            time.sleep(1)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
