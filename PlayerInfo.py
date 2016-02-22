import config
import DateFormatter

'''
This class will be used to feed in information about a player's past stats
as well as the most recent update to their stats, and then determine certain
information like whether to make a change, if that change is add or drop,
how many adds have occured in the last 20 minutes, when was the last time a
note was sent
'''

class PlayerInfo():

    def __init__(self):
        self.todays_date = DateFormatter.DateFormatter()

    def load_player(self, historical_player_json, todays_info_json):
        """
        format of historical_player_json:
        {
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
            },
        }

        format of recent_info_json:

        {
            "drops": <number of drops listed>,
            "adds": <number of adds listed
        }
        """
        self.name = historical_player_json["full_name"]
        self.appearances = historical_player_json["appearances"]
        self.averages = historical_player_json["averages"]
        self.last_date_dict = historical_player_json["last_date"]
        self.old_daily_totals = historical_player_json["total"]

        self.new_daily_totals = todays_info_json

        self.transaction_suggestion = None
        self.stats_over_last_interval = {}

        self.final_update = {}

    def update_player(self):

        if not self.large_polling_gap():
            """
            There has not been a gap between successive appearances on the list
            that is greater than the gaps between polling, implying that
            the numbers involved in this most recent poll can be used
            in the average, information cna be updated and a verdict can be rendered
            """
            # subtract the previous value for adds/drops to get addition to averages

            self.calculate_recent_stats()

            # there are two instances where a transaction verdict of "drop" or "add"
            # will be rendered as opposed to None:
            # 1) the most recent number of adds/drops exceeds the average for this player
            #    by <percent_increase> and the total appearances is greater than <minimum_appearances>
            # 2) adds or drops exceed <percent_of_total> of the total transactions with total
            #    number of transactions exceeding a scaled version of <minimum_transactions_per_hour>

            if self.enough_appearances() and self.significant_transactions_occured():

                print "\tPlayer has made enough appearances and has significant transactions"

                self.get_increased_transaction_suggestion()

            if self.no_suggestion() and self.enough_transactions_occured():
                # this allows control for a newer player who had an inordinately high
                # number of adds/drops in their first few entries, skewing the average
                print "\tPlayer has had enough transactions for a closer look"
                self.get_percentage_transaction_suggestion()

            # calculate new averages
            self.calculate_new_averages()

            self.final_update = self.return_major_update()

        # generate new transactions profile
        else:

            self.final_update = self.return_minor_update()

    def large_polling_gap(self):
        return self.todays_date.time_difference(self.last_date_dict, "minutes") > 
            (config.CONFIG["criteria"]["sampling_interval"] + config.CONFIG["criteria"]["interval_leniency"])

    def do_nothing(self):
        # average_adds = previous_player_stats["averages"]["adds"]
        # average_drops = previous_player_stats["averages"]["drops"]
        # appearances = previous_player_stats["appearances"]
        pass

    def get_new_json(self):
        pass

    def calculate_recent_stats(self):
        self.stats_over_last_interval["adds"] = self.new_daily_totals["adds"] - self.old_daily_totals['adds']
        self.stats_over_last_interval["drops"] = self.new_daily_totals["drops"] - self.old_daily_totals['drops']

    def enough_appearances(self):
        return self.appearances > config.CONFIG["criteria"]["minimum_appearances"]

    def significant_transactions_occured(self):
        # if there are significant adds AND significant drops then the point is possibly moot
        # this will be verified later on    
        enough_adds = self.significant_adds()
        enough_drops = self.significant_drops()

        return ((enough_adds and not enough_drops) or (enough_drops and not enough_adds))

    def significant_adds(self):
        add_percent = (float(self.stats_over_last_interval["adds"]) / self.averages["adds"])
        return add_percent > config.CONFIG["criteria"]["percent_increase"]

    def significant_drops(self):
        drop_percent = (float(self.stats_over_last_interval["drops"]) / self.averages["drops"])
        return drop_percent < config.CONFIG["criteria"]["percent_increase"]

    def get_increased_transaction_suggestion(self):
        if self.player.significant_adds():
            # a spike in adds
            self.transaction_suggestion = "add"
        elif self.player.significant_drops():
            # a spike in drops
            self.transaction_suggestion = "drop"

    def get_percentage_transaction_suggestion(self):
        adds = self.stats_over_last_interval["adds"]
        drops = self.stats_over_last_interval["drops"]
        total = adds + drops

        if (float(adds)/float(total)) > config.CONFIG["criteria"]["percent_of_total"]["adds"]:
            # a significant number of adds
            self.transaction_suggestion = "add"
        elif (float(drops)/float(total)) > config.CONFIG["criteria"]["percent_of_total"]["drops"]:
            # a significant number of drops
            self.transaction_suggestion = "drop"

    def no_suggestion(self):
        return self.transaction_suggestion == None

    def enough_transactions_occured(self):
        total_transactions = self.stats_over_last_interval["adds"] + self.stats_over_last_interval["drops"]
        multiplier = config.CONFIG["criteria"]["sampling_interval"] / 60
        return total_transactions > (config.CONFIG["criteria"]["minimum_transactions"] * multiplier)

    def calculate_new_averages(self):
        lifetime_adds = self.appearances * self.averages["adds"]
        lifetime_drops = self.appearances * self.averages["drops"]
        B = config.CONFIG["criteria"]["beta"]
        # self.averages["adds"] = float(lifetime_adds + self.stats_over_last_interval["adds"])/(self.appearances + 1)
        # self.averages["drops"] = float(lifetime_drops + self.stats_over_last_interval["drops"])/(self.appearances + 1)
        self.averages["adds"] =  (1-B) * self.averages["adds"] + B * self.stats_over_last_interval["adds"]
        self.averages["drops"] =  (1-B) * self.averages["drops"] + B * self.stats_over_last_interval["drops"]

    def return_major_update(self):
        self.appearances += 1
        update = self.return_minor_update()
        update["recent"] = {"adds": self.stats_over_last_interval["adds"],
            "drops": self.stats_over_last_interval["drops"]}

        return update

    def return_minor_update(self):
        update = {}

        update["full_name"] = self.name
        update["appearances"] = self.appearances
        update["averages"] = {"adds": self.averages["adds"], "drops": self.averages["drops"]}
        update["total"] = {"adds": self.new_daily_totals["adds"], "drops": self.new_daily_totals["drops"]}
        update["last_date"] = self.todays_date.date_dict

        return update

    def update_date(self):
        self.todays_date.update()






    