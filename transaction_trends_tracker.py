import requests, re, time, smtplib, sys, datetime, json, os
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from pyvirtualdisplay import Display
import email.message
from bs4 import BeautifulSoup
import pytz
from datetime import date
import config, uuid
# from pygoogle import pygoogle

"""
This script will keep track of all possible players in the transactions list hour over hour
to see if there has been a spike in activity compared to their usual amount of adds
or drops. Should a spike occur, that player is cross referenced with each league to see
if they are being added and are available or if they are being dropped and are on
my team. If either case is true, the player is looked up in a site like rotoworld, their
latest news is recorded and an email is sent to me.

details:
- The transactions are checked on the 19/39/59th minute of every hour (via crontab) and saved 
such that the difference between each interval (with the first 19 of every day assuming a starting
point of 0 adds and 0 drops). 

- the json file containing the add drop statitstics is loaded to see previous information
about adds/drops for each player

- Should a player be seen to be spiking in activity, the link for their player page is used
to find their full name (if it is not already in the system)

- the player name is used in conjunction with google and selenium to search
for "nhl rotoworld <player name>". The first link is obtained from the result and is accessed

- the most recent news item is obtained and used along with the name of the player as
the email paylod

- the email is immediately sent to my email account

json file format

{
    <player name>: {
        "full_name": <full name>
        "appearances": <total number of appearances on list>,
        "averages": {
            "adds": <average adds in interval>,
            "drops": <average drops in interval>
            },
        "last": {
            "day": <day of last poll>
            "adds": <last number of adds from poll>
            "drops": <last number of drops from poll>
            }
        }
    } 
}

"""

no_transactions_string = "Transaction Trend data will be available once player transactions begin."

def main():

    os.chdir('/home/{}/Dropbox/Code/Hockey/transaction_trends'.format(config.CONFIG["usernames"][str(uuid.getnode())]))

    # find the datetime in the eastern time zone and then
    # use this to find today's transactions according to Yahoo
    # print "Obtaining todays datetime"
    date = my_date()
    formatted_date = format_date(date)
    website = config.CONFIG["misc"]["website_prototype"] + formatted_date
    new_transactions = transaction_players(website)
    # print "Obtaining previous json file"
    # obtain the previous transaction information
    previous_transactions = load_json_file(config.CONFIG["misc"]["file_to_store"])
    
    # the dictionary to hold the transaction profiles
    new_json_file = {}
    # the notes to go along with the players who should be dropped or added
    notes_to_send = {}

    if previous_transactions is None:
        # this means there was no previous json file

        print "No existing json\nCreating json file"
        # build the first transactions json
        for player in new_transactions:
            new_json_file[player] = format_new_player_json(new_transactions[player])

    else:
        # there are two possibilities here:
        # 1) a new player for whom a transaction profile must be created, added
        # 2) an existing player, allowing for comparison
        
        # print "Copying previous json"
        # copy the previous transactions to prepare the dictoinary to return
        for item in previous_transactions:
            new_json_file[item] = previous_transactions[item]

        # the new player profiles
        to_add = {}
        # the player profiles being changed
        to_change = {}

        # go through the players listed in the new transactions
        for player in new_transactions:
            # check to see if they exist in the previous file
            if player in previous_transactions:

                # compare the current transaction status with the previous one
                result = compare_transactions(previous_transactions[player], new_transactions[player])

                # add the modified profile to the list to change
                to_change[player] = result[0]


                # check to see if the verdict of the recent change was "add" or "drop."
                # additionally, limit the number of emails sent out regarding a specific
                # player to one per x hours. this does not prevent important information
                # from being sent out, as there must have been an initial notification.
                # this just prevents continual emails
                if (result[1] != None):
                    print "Processing player {}".format(player)
                    
                    sent_notes = compare_notifications(previous_transactions[player], result[1])

                    if not sent_notes:
                        

                        # print "Significant transactions with result: {}".format(result[1])

                        player_notes = availability_notes(previous_transactions[player]\
                            ["full_name"], result[1], new_transactions[player])

                        to_change[player]["last_notification"] = {}
                        to_change[player]["last_notification"]["date"] = make_date_dict(date)
                        to_change[player]["last_notification"]["action"] = result[1]

                        if player_notes:

                            # print "Transaction recommended"

                            notes_to_send[player] = player_notes

                    else:
                        to_change[player]["last_notification"] = previous_transactions[player]["last_notification"]

                if ("last_notification" in previous_transactions[player].keys()) and \
                    ("last_notification" not in to_change[player].keys()):
                    to_change[player]["last_notification"] = previous_transactions[player]["last_notification"]

            else:
                print "Creating profile for player {}".format(player)
                # create a new transaction profile for this player
                # who will be added to the transactions json
                to_add[player] = format_new_player_json(new_transactions[player])

        

        for player in to_change:
            # print "Modifying player profiles"
            new_json_file[player] = to_change[player]

        # add the new transactino profiles
        for player in to_add:
            # print "Adding new players to transactions json"
            new_json_file[player] = to_add[player]

    # print "Writing to json file"
    write_json_file(new_json_file, config.CONFIG["misc"]["file_to_store"])

    if notes_to_send:
        # print "Actions recommended, sending email"
        send_email(notes_to_send)


    # important_transactions = pare_transactions(transactions, threshold)

def format_date(date):

    """
    formatted date must be in the form of
    YYYY-MM-DD
    taking great care that the month and day are two digits long
    i.e. 1998-09-02
    """

    year = date.year
    month = date.month
    if month < 10:
        month = "0{}".format(month)
    day = date.day
    if day < 10:
        day = "0{}".format(day)

    # date_dict = {"day": day, "month": month, "year": year}

    return "{0}-{1}-{2}".format(year,month,day)

def make_date_dict(date):

    year = date.year
    month = date.month
    day = date.day
    hour = date.hour
    minute = date.minute


    date_dict = {"day": day, "month": month, "year": year, "hour":hour, "minute": minute}

    return date_dict

def compare_notifications(player_profile, decision):

    print "Testing if previous notifications exist and meet qualifications"

    result = False
    current_date_dict = make_date_dict(my_date())


    # this player has previously had a notification
    if "last_notification" in player_profile:
        print "1) There was a previous notification. Continuing"
        # less than <mininum_hours> have passed since the last notification:
        if time_difference(current_date_dict, \
            player_profile["last_notification"]["date"],"hours") < config.CONFIG["criteria"]["minimum_hours"]:
            print "2) This notification was {0} hours ago, which is less than {1} hours. Continuing".format(\
                time_difference(current_date_dict, player_profile["last_notification"]["date"],"hours"),\
                config.CONFIG["criteria"]["minimum_hours"])
            # the recommended action was the same as it is now
            if player_profile["last_notification"]["action"] == decision:
                print "3) The last notification was the same as this notification. Do not send another email"
                result = True

    if not result:
        print "current date dict:\n"
        print_json(current_date_dict)

        print "\nplayer profile:\n"
        print_json(player_profile)
        

    return result

def my_date():
    return datetime.datetime.now(pytz.timezone('US/Eastern'))

def availability_notes(player_name, result, player_profile):

    # determine the player's status in each league

    availability = league_availability(player_name)
    # print "Availability:\n"
    # print_json(availability)
    """
    format:
    {
        <league name>: <"on team"/"available"/None>
    }
    """
    # print "verdict: {}".format(result)

    notes_to_send = {}

    if ((result == "add") and ("available" in availability.values())) or \
        ((result == "drop") and ("on team" in availability.values())):

        # obtain the note for the player on rotoworld
        notes_to_send["note"] = player_notes(player_name)

        # the verdict
        notes_to_send["verdict"] = result
        notes_to_send["stats"] = {"adds": player_profile["adds"],"drops": player_profile["drops"]}
        notes_to_send["leagues"] = {}

        for league in config.CONFIG["leagues"]:
            if ((result == "add") and (availability[league] == "available")):
                notes_to_send["leagues"][league] = config.CONFIG["leagues"][league]                                
            elif ((result == "drop") and (availability[league] == "on team")):
                notes_to_send["leagues"][league] = config.CONFIG["leagues"][league]

    return notes_to_send

def league_availability(player_name):

    name_list = re.split(" ", player_name)
    search_term = "+".join(name_list)

    to_return = {}

    #return {<league name>: <"on team"/"available"/None>}
    for league in config.CONFIG["leagues"]:
        # print "Finding player availability in {}".format(league)
        search_link = config.CONFIG["leagues"][league] + "playersearch?&search=" + search_term
        print search_link

        r = requests.get(search_link)
        soup = BeautifulSoup(r.content,'html.parser')
        owner = soup.findAll("div",{"style": "text-overflow: ellipsis; overflow: hidden;"})
        # for item in owner:
        #     print item.prettify()

        owner = str(owner[1].find(text=True))
        
        if owner == "FA":
            to_return[league] = "available"
        elif owner == config.CONFIG["teams"][league]:
            to_return[league] = "on team"
        else:
            to_return[league] = None

    return to_return

def send_email(notes_to_send):
    print "Preparing email"
    m = email.message.Message()
    m['From'] = config.CONFIG["email"]["address"]
    m['To'] = config.CONFIG["email"]["address"]
    m['Subject'] = "Notable player transactions"

    header = "Notes\n---------------------------------------\n"

    my_payload = get_email_string(notes_to_send)

    m.set_payload(my_payload)

    try:
        # print("trying host and port...")

        smtpObj = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        smtpObj.login("alfred.e.kenny@gmail.com", config.CONFIG["email"]["app_pw"])

        # print("sending mail...")

        smtpObj.sendmail(config.CONFIG["email"]["address"], 
            config.CONFIG["email"]["address"], m.as_string())

        # print("Succesfully sent email")

    except smtplib.SMTPException:
        print("Error: unable to send email")
        import traceback
        traceback.print_exc()

def time_difference(later_date, earlier_date,diff_type):


    later = datetime.datetime(int(later_date["year"]),int(later_date["month"]), int(later_date["day"]), 
        int(later_date["hour"]), int(later_date["minute"]))

    earlier = datetime.datetime(int(earlier_date["year"]), int(earlier_date["month"]), int(earlier_date["day"]),
        int(earlier_date["hour"]), int(earlier_date["minute"]))

    difference = later - earlier

    if diff_type == "minutes" :

        result = float(difference.seconds)/60

    elif diff_type == "hours":

        result = float(difference.seconds)/3600

    elif diff_type == "days":

        result = difference.days

    return result       

def get_email_string(notes):
    """
    notes format:
    {
        <player name>: {
            "note": <player note>,
            "verdict": <"add"/"drop">
            "leagues": {
                <league name>: <link>,
                <league name>: <link>
            }
        }
    }
    """

    # print "Formulating email"



    email_string = []

    for player in notes:

        print_json(notes[player])
        

        player_string = []
        # print player
        # print_json(notes[player])
        player_string.append("\n\nRecommendation for {}:\n\n".format(player)) 
        player_string.append("Today's stats:\nAdds: {0}, Drops: {1}\n".format(notes[player]["stats"]["adds"],
            notes[player]["stats"]["drops"]))   
        player_string.append("Action: {}\n\n".format(notes[player]["verdict"]))

        leagues = []
        for league in notes[player]["leagues"]:
            leagues.append("{0}: {1}".format(league,notes[player]["leagues"][league]))

        player_string.append("Leagues:\n{}\n".format("\n".join(leagues)))
        player_string.append("Rotowire notes:\n{}\n\n".format(notes[player]["note"]))

        email_string.append("".join(player_string))

    return "------------------------------------------------".join(email_string)

def player_notes(player_name):
    # Obtain notes from player on rotoworld.com

    # print "Searching for notes from rotoworld"

    name_parts = re.split('\W+', player_name)
    google_search = "http://www.google.com/search?start=0&num=1&q={}+site:rotoworld.com".format(
        "+".join(name_parts))
    r = requests.get(google_search)
    soup = BeautifulSoup(r.content,'html.parser')
    link = soup.find("h3",{"class":"r"})
    hlink = link.find("a")["href"]
    search_link = str(re.split("=",re.split("&",hlink)[0])[1])
    r = requests.get(search_link)
    soup = BeautifulSoup(r.content,'html.parser')
    info = soup.find("div",{"class":"playernews"})
    report = info.find("div",{"class":"report"})
    impact = info.find("div",{"class":"impact"})
    note = report.contents[0] + " " + impact.contents[0]

    return note


def compare_transactions(previous, new):
    # return the new player transaction json as well as a decision (add/drop/nothing)

    """
    format of previous:
    {
        "full_name": <player's full name>
        "appearances": <total number of appearances on list>,
        "averages": {
            "adds": <average adds in interval>,
            "drops": <average drops in interval>
        },
        "last": {
            "date": {
                "year": <year>,
                "month": <month>,
                "day": <day
            },
            "adds": <last number of adds from poll>,
            "drops": <last number of drops from poll>
        }
    }

    format of new:

    {
        "drops": <number of drops listed>,
        "adds": <number of adds listed
    }
    """

    to_return = {}
    to_return["full_name"] = previous["full_name"]

    # this date is important; when compared to the previous
    # datapoint's date in previous, it shows if the "last" add/drop
    # values should be diregarded based on a difference in days
    current_datetime = my_date()
    date_dict = make_date_dict(current_datetime)

    if time_difference(date_dict, previous["last"]["date"], "minutes") > 30:
        """
        There has been a gap between successive appearances on the list
        that is greater than the gaps between polling, implying that
        the numbers involved in this most recent poll should not be used
        in the average. Instead, the appearances value will not be incremented
        and the only change will be that the values for last poll datetime
        and last poll adds/drops will be updated to be used for the next poll.
        """

        average_adds = previous["averages"]["adds"]
        average_drops = previous["averages"]["drops"]
        appearances = previous["appearances"]

        verdict = None

    else:
        # subtract the previous value for adds/drops to get addition to averages

        adds = new["adds"] - previous['last']['adds']
        drops = new["drops"] - previous['last']['drops']


        # there are two instances where a transaction verdict of "drop" or "add"
        # will be rendered as opposed to None:
        # 1) the most recent number of adds/drops exceeds the average for this player
        #    by <percent_increase> and the total appearances is greater than <minimum_appearances>
        # 2) adds or drops exceed <percent_of_total> of the total transactions with total
        #    number of transactions exceeding <minimum_transactions>

        appearances = previous["appearances"]

        verdict = None

        if appearances > config.CONFIG["criteria"]["minimum_appearances"]:

            add_percent = (float(adds)/previous["averages"]["adds"])
            drop_percent = (float(drops)/previous["averages"]["drops"])

            if (add_percent < config.CONFIG["criteria"]["percent_increase"] or \
                drop_percent < config.CONFIG["criteria"]["percent_increase"]):

                if add_percent > config.CONFIG["criteria"]["percent_increase"]:
                    # a spike in adds
                    verdict = "add"
                elif drop_percent > config.CONFIG["criteria"]["percent_increase"]:
                    # a spike in drops
                    verdict = "drop"

        if ((adds+drops) > config.CONFIG["criteria"]["minimum_transactions"]) and verdict == None:
            # this allows control for a newer player who had an inordinately high
            # number of adds/drops in their first few entries, skewing the average

            total = adds + drops

            if (float(adds)/float(total)) > config.CONFIG["criteria"]["percent_of_total"]["adds"]:
                # a significant number of adds
                verdict = "add"
            elif (float(drops)/float(total)) > config.CONFIG["criteria"]["percent_of_total"]["drops"]:
                # a significant number of drops
                verdict = "drop"

        # calculate new averages
        average_adds = float((appearances * previous["averages"]["adds"]) + adds)/(appearances + 1)
        average_drops = float((appearances * previous["averages"]["drops"]) + drops)/(appearances + 1)

        appearances += 1

    # generate new transactions profile
    to_return["appearances"] = appearances
    to_return["averages"] = {"adds": average_adds, "drops": average_drops}
    to_return["last"] = {"date": date_dict, "adds": new["adds"], "drops": new["drops"]}

    return [to_return, verdict]


def format_new_player_json(player):
    """
    <player name>: {
        "full_name": <player's full name>
        "appearances": <total number of appearances on list>,
        "averages": {
            "adds": <average adds in interval>,
            "drops": <average drops in interval>
        },
        "last": {
            "date": <datetime of last poll>
            "adds": <last number of adds from poll>
            "drops": <last number of drops from poll>
        }
    }
    """

    current_datetime = my_date()
    date_dict = make_date_dict(current_datetime)

    player_json = {}
    player_json["full_name"] = full_name(player["player_page"])
    player_json["appearances"] = 0
    # we can't have any averages yet since this is the first time
    # seeing this player
    player_json["averages"] = {"adds": 0, "drops": 0}
    player_json["last"] = {
                            "date": date_dict,
                            "adds": player["adds"],
                            "drops": player["drops"]
                            }

    return player_json

def full_name(player_link):

    # print "Obtaining full name of player in link {}".format(player_link)

    # now we look for the full name in case we want to search
    # elsewhere on the internet for info
    try:
        soup = BeautifulSoup(requests.get(player_link).content,'html.parser')
        name = str(soup.find('div',{'class':'player-info'}).find('h1').contents[0])
    except:
        # wait and use recursion to try again to get the name
        e = sys.exc_info()[0]
        print e
        time.sleep(3)
        name = full_name(player_link)

    return name

def transaction_players(website):
    # obtain webpage for yahoo transactions
    # print "Finding today's transactions from Yahoo"

    r = requests.get(website)

    # find all players in webpage
    soup = BeautifulSoup(r.content,'html.parser')
    table = soup.find("table",{"class": "Tst-table Table"}).tbody
    players = table.findAll('tr')

    # where we will hold all the players in the dictionary to return
    transactions_dict = {}

    for player in players:
        # we just need:
        # 1) name for referencing on different sites
        # 2) drops for seeing if we should move the player
        # 3) adds for seeing if we should get the player

        # the full html link
        if str(player.find(text=True)) == no_transactions_string:
            print "No transactions yet today"
            sys.exit(1)

        html_link = player.findAll('a')[1]
        # just the link string
        name_link = html_link['href']

        # find the contents of the player line
        add_drop_info = player.findAll('td')
        drops = int(add_drop_info[1].contents[0].contents[0])
        adds = int(add_drop_info[2].contents[0].contents[0])

        transactions_dict[str(html_link.contents[0])] = {"drops":drops, "adds":adds, 
            "player_page": name_link}

    return transactions_dict

def pare_transactions(transactions, percentage_threshold, number_threshold = 0):

    important_transactions = []

    for player in transactions:
        total_transactions = float(player["adds"] + player["drops"])
        if total_transactions < number_threshold:
            continue

        percentage = player["adds"]/total_transactions

        if percentage > percentage_threshold:
            player["decision"] = "add"
        elif percentage < (1-percentage_threshold):
            player["decision"] = "drop"
        else:
            continue

        important_transactions.append(player)

    return important_transactions

def print_json(json_object):
    print json.dumps(json_object, indent=4, sort_keys=True) 
    print "\n"

def load_json_file(file_name):

    data = None

    try:
        with open(file_name) as data_file:
                data = json.load(data_file)
    except:
        pass

    return data

def write_json_file(transactions_dict, file_name):
    with open(file_name,'w') as outfile:
        json.dump(transactions_dict, outfile, indent=4, sort_keys=True)

if __name__ == "__main__":

    os.chdir('/home/{}/Dropbox/Code/Hockey/transaction_trends'.format(config.CONFIG["usernames"][str(uuid.getnode())]))
    main()