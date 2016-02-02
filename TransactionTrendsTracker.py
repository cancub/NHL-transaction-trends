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
import DateFormatter
import NoteDatabase
import PlayerInfo
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

class TransactionTrendsTracker():

    def __init__(self):
        os.chdir('/home/{}/Dropbox/Code/Hockey/transaction_trends'.format(config.CONFIG["usernames"][str(uuid.getnode())]))
        self.my_date = DateFormatter.DateFormatter()
        self.new_transactions = self.transaction_players()
        self.previous_transactions = self.load_json_file()
        self.note_database = NoteDatabase.NoteDatabase()
        self.notes_to_send = {}
        self.player = PlayerInfo.PlayerInfo()

    def run(self):        
        

        if self.previous_transactions is None:
            # this means there was no previous json file
            json_to_write = self.create_new_transactions_json()

        else:
            # there are two possibilities here:
            # 1) a new player for whom a transaction profile must be created, added
            # 2) an existing player, allowing for comparison
            
            json_to_write = self.obtain_modified_transactions_json()

        # print "Writing to json file"
        self.write_json_file(json_to_write, config.CONFIG["misc"]["file_to_store"])

        if self.notes_to_send:
            # print "Actions recommended, sending email"
            self.send_email(notes_to_send)

    def create_new_transactions_json(self):

        print "No existing json\nCreating json file"
        new_json_file = {}
        # build the first transactions json
        for player in self.new_transactions:
            new_json_file[player] = self.format_new_player_json(self.new_transactions[player])

        return new_json_file

    def obtain_modified_transactions_json(self):
        # print "Copying previous json"
        # copy the previous transactions to prepare the dictoinary to return
        transaction_json_draft = copy_dictionary(self.previous_transactions)

        # the new player profiles
        to_add = {}
        # the player profiles being changed
        to_change = {}

        # checker = AddDropChecker.AddDropChecker(self.previous_transactions, self.new_transactions)

        # go through the players listed in the new transactions
        for player in self.new_transactions:
            # check to see if they exist in the previous file
            if self.player_already_exists(player):

                # load the player's stats into the parser
                self.player.load_player(self.previous_transactions[player], self.new_transactions[player])

                # compare the current transaction status with the previous one
                self.player.update_player()

                # add the modified profile to the list to change
                to_change[player] = self.player.final_update


                # check to see if the verdict of the recent change was "add" or "drop."
                # additionally, limit the number of emails sent out regarding a specific
                # player to one per x hours. this does not prevent important information
                # from being sent out, as there must have been an initial notification.
                # this just prevents continual emails
                if (self.player.transation_suggestion != None):
                    print "Processing player {}".format(player)
                    
                    sent_notes = compare_notifications(previous_transactions[player], result[1])

                    if not sent_notes:
                        

                        # print "Significant transactions with result: {}".format(result[1])

                        player_notes = availability_notes(previous_transactions[player]\
                            ["full_name"], result[1], new_transactions[player])

                        to_change[player]["last_notification"] = {}
                        to_change[player]["last_notification"]["date"] = self.my_date.date_dict
                        to_change[player]["last_notification"]["action"] = result[1]

                        if player_notes:

                            # print "Transaction recommended"

                            self.notes_to_send[player] = player_notes

                    else:
                        to_change[player]["last_notification"] = previous_transactions[player]["last_notification"]

                if ("last_notification" in previous_transactions[player].keys()) and \
                    ("last_notification" not in to_change[player].keys()):
                    to_change[player]["last_notification"] = previous_transactions[player]["last_notification"]

            else:
                print "Creating profile for player {}".format(player)
                # create a new transaction profile for this player
                # who will be added to the transactions json
                to_add[player] = self.format_new_player_json(self.new_transactions[player])

        
        final_json = self.combine_changes(new_json_file, to_change, to_add)

        return final_json

    def copy_dictionary(old_dict):
        new_dict = {}
        for item in old_dict:
            new_dict[item] = old_dict[item]

        return new_dict

    def player_already_exists(self, player_name):
        return player_name in self.previous_transactions

    def combine_changes(self, ):
        for player in to_change:
            # print "Modifying player profiles"
            new_json_file[player] = to_change[player]

        # add the new transactino profiles
        for player in to_add:
            # print "Adding new players to transactions json"
            new_json_file[player] = to_add[player]

    def compare_notifications(self, player_profile, decision):

        print "Testing if previous notifications exist and meet qualifications"

        result = False

        # this player has previously had a notification
        if "last_notification" in player_profile:
            print "1) There was a previous notification. Continuing"
            # less than <mininum_hours> have passed since the last notification:
            if time_difference(self.my_date.date_dict, \
                player_profile["last_notification"]["date"],"hours") < config.CONFIG["criteria"]["minimum_hours"]:
                print "2) This notification was {0} hours ago, which is less than {1} hours. Continuing".format(\
                    time_difference(self.my_date.date_dict, player_profile["last_notification"]["date"],"hours"),\
                    config.CONFIG["criteria"]["minimum_hours"])
                # the recommended action was the same as it is now
                if player_profile["last_notification"]["action"] == decision:
                    print "3) The last notification was the same as this notification. Do not send another email"
                    result = True

        if not result:
            print "current date dict:\n"
            print_json(self.my_date.date_dict)

            print "\nplayer profile:\n"
            print_json(player_profile)
            

        return result

    def availability_notes(self, player_name, result, player_profile):

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

    def league_availability(self, player_name):

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

    def player_notes(self, player_name):
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
                "date": <datetime of last poll>
                "adds": <last number of adds from poll>
                "drops": <last number of drops from poll>
            }
        }
        """

        player_json = {}
        player_json["full_name"] = full_name(player["player_page"])
        player_json["appearances"] = 0
        # we can't have any averages yet since this is the first time
        # seeing this player
        player_json["averages"] = {"adds": 0, "drops": 0}
        player_json["total"] = {
                                "date": self.my_date.date_dict,
                                "adds": player["adds"],
                                "drops": player["drops"]
                                }

        return player_json

    def full_name(self, player_link):

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

    def transaction_players(self):
        # obtain webpage for yahoo transactions
        # print "Finding today's transactions from Yahoo"

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

    def pare_transactions(self, transactions, percentage_threshold, number_threshold = 0):

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

    def send_email(self,notes_to_send):
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

    def get_email_string(self, notes):
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


    def print_json(self, json_object):
        print json.dumps(json_object, indent=4, sort_keys=True) 
        print "\n"

    def load_json_file(self, file_name):

        data = None

        try:
            with open(file_name) as data_file:
                    data = json.load(data_file)
        except:
            pass

        return data

    def write_json_file(self, transactions_dict, file_name):
        with open(file_name,'w') as outfile:
            json.dump(transactions_dict, outfile, indent=4, sort_keys=True)

if __name__ == "__main__":

    os.chdir('/home/{}/Dropbox/Code/Hockey/transaction_trends'.format(config.CONFIG["usernames"][str(uuid.getnode())]))
    tracker = TransactionTrendTracker()
    tracker.run()