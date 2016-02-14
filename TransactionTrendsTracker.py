import requests, re, time, smtplib, sys, datetime, json, os, argparse
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from pyvirtualdisplay import Display
import email.message
from bs4 import BeautifulSoup
import pytz
from datetime import date
import config, uuid
import DateFormatter
import NoteManager
import PlayerInfo
import LeagueMonitor
import JSONTool
import EmailTool
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
    ...,
    <player name>: {
        "full_name": <player's full name>
        "appearances": <total number of appearances on list>,
        "averages": {
            "adds": <average adds in interval>,
            "drops": <average drops in interval>
        },
        "recent": {
            "adds": <number of adds in last period reviewed>,
            "drops": <number of drops in last period reviewed>
        },
        "total": {
            "adds": <overall number of adds today>, 
            "drops": <overall number of drops today>
        },
        "last_date": {
            "year": <year of last review>,
            "month": <month of last review>,
            "day": <day of last review>
        }
    },
    ...
}

"""

verbose = True

def verbose_print(statement):
    if verbose:
        print "{}\n".format(statement)

class TransactionTrendsTracker():

    def __init__(self):
        os.chdir('/home/{}/Dropbox/Code/Hockey/Transaction_trends/Development'.format(config.CONFIG["usernames"][str(uuid.getnode())]))
        self.my_date = DateFormatter.DateFormatter()
        self.json_tool = JSONTool.JSONTool(config.CONFIG["misc"]["file_to_store"])
        self.email_tool = EmailTool.EmailTool()
        self.league_monitor = LeagueMonitor.LeagueMonitor()
        self.player = PlayerInfo.PlayerInfo()
        self.note_manager = NoteManager.NoteManager()

        self.transactions_json = None
        self.new_transactions = None

        self.notes_on_hold = {}  

        self.pending_player_changes = {}
        self.pending_player_additions = {}  

        self.next_sample_time = None

    def run(self): 

        self.load_transactions_json()

        if self.transactions_json is None:
            # this means there was no previous json file
            self.next_sample_time = datetime.datetime.now() + datetime.timedelta(minutes = 20)
            self.create_new_transactions_json()
            self.json_tool.write_file({"date_dict": self.my_date.date_dict, "players":self.transactions_json})

        while True:

            self.sleep_until_next_polling_time()

            self.pull_new_transactions()

            self.obtain_modified_transactions_json()

            if self.new_player_notes_exist():
                verbose_print("Actions recommended, sending email")
                # modify notes_on_hold to contain the notes and league availability
                self.prepare_notes_to_send()
                # change the date dictionary for the last update on each player in transactions_json
                self.update_json_timestamps()
                summary = self.obtain_notes_summary()
                self.email_tool.send_email(summary)

            # should change this to a database
            verbose_print("Writing modified transactions to json file")
            self.json_tool.write_file({"date_dict": self.my_date.date_dict, "players":self.transactions_json})

            self.clear_session_information()

    def load_transactions_json(self):
        my_json = self.json_tool.read_file()


        if my_json:            
            date_dict = my_json["date_dict"]
            self.transactions_json = my_json["players"]
            self.next_sample_time = datetime.datetime(date_dict["year"],
                date_dict["month"],
                date_dict["day"], 
                date_dict["hour"],
                date_dict["minute"]) + datetime.timedelta(minutes = 20)
        else:
            self.next_sample_time = None
            self.transactions_json = None

    def create_new_transactions_json(self):

        print "No existing json. Creating json file"
        self.pull_new_transactions()
        self.transactions_json = {}
        count = 1
        total = len(self.new_transactions)
        # build the first transactions json
        for player in self.new_transactions:
            
            verbose_print("Working on player {0} of {1}: {2}".format(count, total, player))
            self.transactions_json[player] = self.format_new_player_json(self.new_transactions[player])
            count += 1

    def sleep_until_next_polling_time(self):

        if self.next_sample_time and (self.next_sample_time > datetime.datetime.now()):
            # sleep for the difference in seconds between then and now
            time_difference = self.next_sample_time - datetime.datetime.now()
            verbose_print("Sleeping until {0}:{1}".format(self.next_sample_time.hour,
                self.next_sample_time.minute))
            time.sleep(time_difference.seconds)
            self.next_sample_time = self.next_sample_time + datetime.timedelta(minutes=20)
        else:
            self.next_sample_time = datetime.datetime.now() + datetime.timedelta(minutes=20)


    def pull_new_transactions(self):
        # obtain webpage for yahoo transactions
        verbose_print("Finding today's transactions from Yahoo")

        no_transactions_string = "Transaction Trend data will be available once player transactions begin."

        r = requests.get(config.CONFIG["misc"]["website_prototype"] + self.my_date.formatted_date)

        # find all players in webpage
        soup = BeautifulSoup(r.content,'html.parser')
        table = soup.find("table",{"class": "Tst-table Table"}).tbody
        player_blocks = table.findAll('tr')

        # where we will hold all the players in the dictionary to return
        self.new_transactions = {}

        for block in player_blocks:
            # we just need:
            # 1) name for referencing on different sites
            # 2) drops for seeing if we should move the player
            # 3) adds for seeing if we should get the player

            # the full html link
            if str(block.find(text=True)) == no_transactions_string:
                print "No transactions yet today"
                sys.exit(1)

            html_link = block.findAll('a')[1]
            # just the link string
            name_link = html_link['href']

            # find the contents of the player line
            add_drop_info = block.findAll('td')
            drops = int(add_drop_info[1].contents[0].contents[0])
            adds = int(add_drop_info[2].contents[0].contents[0])

            player_name = str(html_link.contents[0])

            self.new_transactions[player_name] = {"drops":drops, "adds":adds, 
                "player_page": name_link}

    def obtain_modified_transactions_json(self):
        # there are two possibilities here:
        # 1) a new player for whom a transaction profile must be created, added
        # 2) an existing player, allowing for comparison
        
        verbose_print("Obtaining modified transaction json\nCopying previous json")
        # copy the previous transactions to prepare the dictoinary to return
        # transaction_json_draft = self.copy_dictionary(self.transactions_json)

        count = 1
        total = len(self.new_transactions)

        # go through the players listed in the new transactions
        for player in self.new_transactions:
            verbose_print("Working on player {0} of {1}: {2}".format(count,total,player))
            # check to see if they exist in the previous file
            if self.player_already_exists(player):
                verbose_print("\tPlayer exists in previous json")

                # load the player's stats into the parser
                self.player.load_player(self.transactions_json[player], self.new_transactions[player])

                # compare the current transaction status with the previous one
                self.player.update_player()

                # add the modified profile to the list to change
                self.pending_player_changes[player] = self.player.final_update

                self.json_tool.print_json(self.player.final_update)


                # check to see if the verdict of the recent change was "add" or "drop."
                # additionally, limit the number of emails sent out regarding a specific
                # player to one per x hours. this does not prevent important information
                # from being sent out, as there must have been an initial notification.
                # this just prevents continual emails
                if (self.player.transaction_suggestion != None):

                    # the only information that should be stored is the date and the 
                    # action that should be taken on the player

                    self.notes_on_hold[player] = self.player.transaction_suggestion

            else:
                verbose_print("\tCreating profile for player {}".format(player))
                # create a new transaction profile for this player
                # who will be added to the transactions json
                self.pending_player_additions[player] = self.format_new_player_json(self.new_transactions[player])

            count += 1

        self.combine_changes()

    def copy_dictionary(self, old_dict):
        new_dict = {}
        for item in old_dict:
            new_dict[item] = old_dict[item]

        return new_dict

    def player_already_exists(self, player_name):
        return player_name in self.transactions_json

    def combine_changes(self):
        verbose_print("Combining changes to players and new additions")
        for player in self.pending_player_changes:
            # print "Modifying player profiles"
            self.transactions_json[player] = self.pending_player_changes[player]

        # add the new transactino profiles
        for player in self.pending_player_additions:
            # print "Adding new players to transactions json"
            self.transactions_json[player] = self.pending_player_additions[player]

    def obtain_notes_summary(self):

        """
        notes_on_hold:
        {
            <player_name>: {
                "verdict": <suggestion for player>
                "note": <note from website>,
                "leagues":{
                    <league name>: <link>,
                    ...
                }
            },
            ...
        }

        json format:
        {
            ...,
            <player name>: {
                "full_name": <player's full name>
                "appearances": <total number of appearances on list>,
                "averages": {
                    "adds": <average adds in interval>,
                    "drops": <average drops in interval>
                },
                "recent": {
                    "adds": <number of adds in last period reviewed>,
                    "drops": <number of drops in last period reviewed>
                },
                "total": {
                    "adds": <overall number of adds today>, 
                    "drops": <overall number of drops today>
                },
                "last_date": {
                    "year": <year of last review>,
                    "month": <month of last review>,
                    "day": <day of last review>
                }
            },
            ...
        }
        """

        # 

        email_string = []

        for player in self.notes_on_hold:

            print_json(self.notes_on_hold[player])

            notes_to_send["stats"] = self.transactions_json[player]["recent"]            

            player_string = []
            # print player
            # print_json(notes[player])
            player_string.append("\n\nRecommendation for {}:\n\n".format(player)) 
            player_string.append("Today's stats:\nAdds: {0}, Drops: {1}\n".format(self.transactions_json[player]["total"]["adds"],
                self.transactions_json[player]["total"]["drops"]))   
            player_string.append("Action: {}\n\n".format(self.notes_on_hold[player]["verdict"]))

            leagues = []
            for league in self.notes_on_hold[player]["leagues"]:
                leagues.append("{0}: {1}".format(league,self.notes_on_hold[player]["leagues"][league]))

            player_string.append("Leagues:\n{}\n".format("\n".join(leagues)))
            player_string.append("Rotowire notes:\n{}\n\n".format(self.notes_on_hold[player]["note"]))

            email_string.append("".join(player_string))

        return "------------------------------------------------".join(email_string)

    def prepare_notes_to_send(self):

        """
        notes_on_hold should look like this following this function:
        {
            <player_name>: {
                "note": <note from website>,
                "leagues":{
                    <league name>: <link>,
                    ...
                }
            },
            ...
        }

        """

        for player in self.notes_on_hold:

            verbose_print("Processing player {}".format(player))                  

            player_notes = self.league_monitor.get_availability_notes(self.transactions_json[player]["full_name"], 
                self.notes_on_hold[player])

            if player_notes:
                self.notes_on_hold[player] = player_notes
            else:
                del self.notes_on_hold[player]

    def new_player_notes_exist(self):

        # go through all the notes to see if there is one player who matches
        # one of the following options:
        #   - the haven't ever had a notification
        #   - the previous notification was long ago
        #   - the previous notification was different
        result = False
        for player in self.notes_on_hold:

            player_profile = self.transactions_json[player]
            decision = self.notes_on_hold[player]

            verbose_print("Testing if previous notifications exist and meet qualifications")


            """
            if there was no previous notification for this player
                there is a new
            """

            if "last_notification" not in player_profile:
                # this player has not previously had a notification
                result = True
                break
            else:
                hour_difference = self.my_date.time_difference(player_profile["last_notification"]["date"],
                    "hours")
                if hour_difference > config.CONFIG["criteria"]["minimum_hours"]:
                    # more than <mininum_hours> have passed since the last notification:
                    result = True
                    break
                elif player_profile["last_notification"]["action"] != self.notes_on_hold[player]:
                    # the recommended action was different that it is now                    
                    result = True
                    break

            # if not result and verbose:
            #     print "current date dict:\n"
            #     print_json(self.my_date.date_dict)

            #     print "\nplayer profile:\n"
            #     print_json(player_profile)
            

        return result

    def update_json_timestamps(self):

        for player in self.notes_on_hold:
            self.transactions_json[player]["last_notification"] = {}
            self.transactions_json[player]["last_notification"]["date"] = self.my_date.date_dict
            self.transactions_json[player]["last_notification"]["action"] = self.notes_on_hold[player]

    def format_new_player_json(self, player):
        """
        <player name>: {
            "full_name": <player's full name>
            "appearances": <total number of appearances on list>,
            "averages": {
                "adds": <average adds in interval>,
                "drops": <average drops in interval>
            },
            "total": {
                "adds": <last number of adds from poll>
                "drops": <last number of drops from poll>
            },            
            "last_date": {
                "year": <year of last review>,
                "month": <month of last review>,
                "day": <day of last review>
            },
        }
        """

        player_json = {}
        player_json["full_name"] = self.full_name(player["player_page"])
        player_json["appearances"] = 0
        # we can't have any averages yet since this is the first time
        # seeing this player
        player_json["averages"] = {"adds": 0, "drops": 0}
        player_json["total"] = {
                                "adds": player["adds"],
                                "drops": player["drops"]
                                }
        player_json["last_date"] = self.my_date.date_dict

        return player_json

    def full_name(self, player_link):

        verbose_print("\tObtaining full name of player in link {}".format(player_link))

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

    def transaction_players(self):
        # obtain webpage for yahoo transactions
        verbose_print("Finding today's transactions from Yahoo")

        no_transactions_string = "Transaction Trend data will be available once player transactions begin."

        r = requests.get(config.CONFIG["misc"]["website_prototype"] + self.my_date.formatted_date)

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

    def clear_session_information(self):
        self.new_transactions = None

        self.notes_on_hold = {}  

        self.pending_player_changes = {}
        self.pending_player_additions = {}

if __name__ == "__main__":

    os.chdir('/home/{}/Dropbox/Code/Hockey/Transaction_trends/Development'.format(config.CONFIG["usernames"][str(uuid.getnode())]))
    tracker = TransactionTrendsTracker()
    tracker.run()