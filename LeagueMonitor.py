from bs4 import BeautifulSoup
import re, requests
import config
import PlayerInfo
import NoteManager

class LeagueMonitor():

    def __init__(self):
        self.leagues = config.CONFIG["leagues"]
        self.note_taker = NoteManager.NoteManager()

    def get_availability_notes(self, player_name, player_suggestion):

        # determine the player's status in each league

        availability = self.get_league_availability(player_name)
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

        if self.change_suggested(availability, player_suggestion):

            notes_to_send["verdict"] = player_suggestion

            # obtain the note for the player on rotoworld
            notes_to_send["note"] = self.note_taker.get_player_notes(player_name)

            # the verdict
            notes_to_send["leagues"] = {}

            for league in self.leagues:
                if ((result == "add") and (availability[league] == "available")):
                    notes_to_send["leagues"][league] = self.leagues[league]                                
                elif ((result == "drop") and (availability[league] == "on team")):
                    notes_to_send["leagues"][league] = self.leagues[league]

        return notes_to_send

    def get_league_availability(self, player_name):

        print player_name

        name_list = re.split(" ", player_name)
        search_term = "+".join(name_list)

        to_return = {}

        #return {<league name>: <"on team"/"available"/None>}
        for league in self.leagues:
            # print "Finding player availability in {}".format(league)
            search_link = self.leagues[league] + "playersearch?&search=" + search_term
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

    def change_suggested(self, availability, suggestion):
        should_add = (suggestion == "add") and ("available" in availability.values())
        should_drop = (suggestion == "drop") and ("on team" in availability.values())

        return (should_add or should_drop)